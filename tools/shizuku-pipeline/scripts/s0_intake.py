# -*- coding: utf-8 -*-
"""ステップ0: 取り込み。リポジトリを再帰探索し、命名規則の違いを吸収して data/raw/ に配置する。
使い方:
  python scripts/s0_intake.py --src <リポジトリのルート等>     # 実際にコピー
  python scripts/s0_intake.py --src <...> --dry-run           # 何が認識されるか確認だけ
  python scripts/s0_intake.py --src <...> --verbose           # 無視したファイルも表示

方針（重要）:
  - フォルダ名・ファイル名の形式に依存しない。**info.txt の「動画ID」「投稿日」を正とする**。
  - 字幕は SBV / SRT / VTT のいずれでも可（.ja.sbv.txt / .ja.srt / .ja.srt.txt / _ja_sbv.txt 等の揺れに対応）。
  - 元ファイルは読むだけ。リネームも移動もしない。
"""
import argparse, json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import DATA, read, write, load_known_absent, load_relations

SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", ".venv"}
VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

PATTERNS = [
    ("info",     re.compile(r"(?:^|[._-])info\.txt$")),
    ("comments", re.compile(r"(?:^|[._-])comments?\.txt$")),
    ("chat_ocr", re.compile(r"(?:^|[._-])(?:live[._-]?)?chat[._-]ocr\.txt$")),
    ("chat",     re.compile(r"(?:^|[._-])(?:live[._-]?)?chat\.txt$")),
    ("sbv",      re.compile(r"(?:^|[._-])(?:ja[._-])?sbv(?:\.txt)?$")),
    ("srt",      re.compile(r"(?:^|[._-])(?:ja[._-])?(?:srt|vtt)(?:\.txt)?$")),
]
FOREIGN_RE = re.compile(r"[._-](?:en|en-us|ko|zh|zh-hans|zh-hant|es|fr|de|id|th|vi)[._-](?:sbv|srt|vtt)")
DEST_NAME = {"info": "info.txt", "comments": "comments.txt", "chat": "chat.txt",
             "chat_ocr": "chat_ocr.txt", "sbv": "sbv.txt", "srt": "srt.txt"}
# 欠落の重要度: 字幕は致命的、チャットは重要、コメントは任意（元動画に無いことが普通にある）
SEVERITY = {"字幕": "ERROR", "chat": "WARN", "info": "WARN", "comments": "INFO"}

def classify(name):
    low = name.lower()
    if FOREIGN_RE.search(low): return None
    for kind, rx in PATTERNS:
        if rx.search(low): return kind
    return None

def strip_suffix(name, kind):
    low = name.lower()
    for k, rx in PATTERNS:
        if k == kind:
            m = rx.search(low)
            if m: return name[:m.start()]
    return name

def vid_from_text(s):
    if VID_RE.match(s): return s
    for tok in reversed(re.split(r"[_.\s]+|[（）()【】\[\]]", s)):
        if VID_RE.match(tok): return tok
    return None

def date_from_text(s):
    m = re.search(r"(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

def sniff_x(path):
    try:
        head = read(path)[:400]
    except Exception:
        return None
    first = next((l for l in head.split("\n") if l.strip()), "")
    if "\t" in first and ("URL" in first or "日付" in first): return "tsv"
    if head.strip() in ("なし", "無し", "なし。", ""): return "empty"
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    src = Path(a.src).expanduser().resolve()
    if not src.exists():
        print(f"エラー: {src} が存在しません"); return

    # 事前スキャン: 各ディレクトリのinfo.txt数を数える（1つだけならディレクトリ単位でまとめる）
    info_count = {}
    for f in src.rglob("*"):
        if f.is_file() and not any(p in SKIP_DIRS for p in f.parts) and classify(f.name) == "info":
            info_count[f.parent] = info_count.get(f.parent, 0) + 1

    groups, xcands, ignored, discord, misfiled = {}, [], [], [], []
    for f in sorted(src.rglob("*")):
        if not f.is_file(): continue
        if any(p in SKIP_DIRS for p in f.parts): continue
        parts_low = [p.lower() for p in f.parts]
        kind = classify(f.name)
        if kind:
            if any("discord" in p for p in parts_low):
                discord.append(f); continue
            stem = strip_suffix(f.name, kind)
            fvid = vid_from_text(stem)
            if info_count.get(f.parent, 0) == 1:
                key = ("dir", str(f.parent))          # 1フォルダ=1配信。ファイル名のIDは信用しない
                if fvid: misfiled.append((f, fvid))    # 後でフォルダのIDと突き合わせて警告
            else:
                vid = fvid or vid_from_text(f.parent.name)
                key = ("vid", vid) if vid else ("dir", str(f.parent))
            g = groups.setdefault(key, {"files": {}, "dir": f.parent})
            g["files"].setdefault(kind, f)
        elif f.suffix.lower() in (".txt", ".tsv"):
            if sniff_x(f): xcands.append(f)
            else: ignored.append(f)
        else:
            ignored.append(f)

    resolved, problems = {}, []
    for key, g in groups.items():
        vid = date = title = None
        if "info" in g["files"]:
            txt = read(g["files"]["info"])
            m = re.search(r"^動画ID\s*[:：]\s*(\S+)", txt, re.M);   vid = m.group(1).strip() if m else None
            m = re.search(r"^投稿日\s*[:：]\s*(\S+)", txt, re.M);   date = m.group(1).strip() if m else None
            m = re.search(r"^タイトル\s*[:：]\s*(.+)$", txt, re.M); title = m.group(1).strip() if m else None
        fname_vid = key[1] if key[0] == "vid" else None
        if vid and fname_vid and vid != fname_vid:
            problems.append(f"ID不一致: ファイル名『{fname_vid}』 vs info.txt『{vid}』 → info.txtを採用 ({g['dir'].name})")
        vid = vid or fname_vid
        date = date or date_from_text(g["dir"].name) or date_from_text(next(iter(g["files"].values())).name)
        if not vid:
            problems.append(f"動画IDを特定できず: {g['dir']} （info.txt が無く、ファイル名にもIDが無い）"); continue
        if not date:
            problems.append(f"日付を特定できず: {g['dir']} （info.txt の投稿日もフォルダ名の日付も無い）"); continue
        r = resolved.setdefault(vid, {"date": date, "title": title, "files": {}, "dirs": []})
        r["date"] = r["date"] or date
        r["title"] = r["title"] or title
        r["dirs"].append(str(g["dir"]))
        for k, p in g["files"].items(): r["files"].setdefault(k, p)

    dir2vid = {}
    for vid, r in resolved.items():
        for d in r["dirs"]: dir2vid[d] = vid
    for f, fvid in misfiled:
        owner = dir2vid.get(str(f.parent))
        if owner and fvid != owner:
            problems.append(f"ファイル名に別の動画ID『{fvid}』が含まれます: {f.name[:60]}"
                            f" → この配信({owner})のものとして扱いました。意図した命名か確認してください")

    absent = load_known_absent()
    rels = load_relations()
    print(f"=== 配信ログ（探索: {src}） ===")
    ok = warn = 0
    absent_cands = []
    for vid, r in sorted(resolved.items(), key=lambda kv: kv[1]["date"]):
        dst = DATA / "raw" / "streams" / f"{r['date']}_{vid}"
        has = r["files"]
        sub = "sbv" if "sbv" in has else ("srt" if "srt" in has else None)
        chat_src = "live" if "chat" in has else ("ocr" if "chat_ocr" in has else None)
        missing = []
        if not sub: missing.append("字幕")
        if "info" not in has: missing.append("info")
        if not chat_src: missing.append("chat")
        if "comments" not in has: missing.append("comments")
        known = [m for m in missing if (vid, m) in absent]
        missing = [m for m in missing if m not in known]
        lv = max([SEVERITY.get(m, "WARN") for m in missing], key=lambda s: ["INFO","WARN","ERROR"].index(s)) if missing else None
        status = {"ERROR": "欠落", "WARN": "不足", "INFO": "OK  ", None: "OK  "}[lv]
        for m in missing:
            if SEVERITY.get(m) != "INFO": absent_cands.append(f"{vid}\t{m}\t（理由をここに書く）")
        acts = []
        if not a.dry_run:
            dst.mkdir(parents=True, exist_ok=True)
            for k, p in has.items():
                d = dst / DEST_NAME[k]
                if d.exists() and d.stat().st_size == p.stat().st_size: continue
                shutil.copy(p, d); acts.append(DEST_NAME[k])
            write(dst / "origin.json", json.dumps(
                {"video_id": vid, "date": r["date"], "title": r["title"],
                 "source_dirs": r["dirs"], "files": {k: str(v) for k, v in has.items()},
                 "subtitle_format": sub, "chat_source": chat_src,
                 "relation": rels.get(vid)}, ensure_ascii=False, indent=1))
        note = f"字幕={sub or 'なし'}"
        if "sbv" in has and "srt" in has: note += "(srtも有→sbv優先)"
        if chat_src == "ocr": note += " / チャット=OCR復元"
        if vid in rels: note += f" / {rels[vid]['rel']}:{rels[vid]['other']}"
        if acts: note += f" / 取込:{','.join(acts)}"
        elif not a.dry_run: note += " / 既存と同一(スキップ)"
        print(f"  [{status}] {r['date']}_{vid}  {note}")
        if missing:
            tag = {"ERROR": "※要対応", "WARN": "※不足", "INFO": "※任意データ無し"}[lv]
            print(f"          {tag}: {', '.join(missing)}   元: {Path(r['dirs'][0]).name[:44]}")
        if known: print(f"          ・既知の不在: {', '.join(known)}（known_absent.tsv に登録済み）")
        ok += 1; warn += bool(missing)

    print("=== Xログ ===")
    for f in xcands:
        kindx = sniff_x(f)
        if not a.dry_run:
            d = DATA / "raw" / "x" / f.name
            if not (d.exists() and d.stat().st_size == f.stat().st_size):
                d.parent.mkdir(parents=True, exist_ok=True); shutil.copy(f, d)
        print(f"  [{'OK  ' if kindx=='tsv' else '空  '}] {f.name}" +
              ("" if kindx == "tsv" else "  ※中身が「なし」＝記録上の空。休眠期なら正常（DATA-ISSUES §6）"))

    if discord:
        print(f"=== Discord ({len(discord)}ファイル) ===\n  未対応のためスキップ（将来の拡張ポイント）")
    if problems:
        print("=== 要確認 ===")
        for p in problems: print("  ! " + p)
    if a.verbose and ignored:
        print(f"=== 無視したファイル（{len(ignored)}件） ===")
        for f in ignored[:40]: print("  -", f.relative_to(src))
    elif ignored:
        print(f"（対象外ファイル {len(ignored)}件は無視。内訳を見るには --verbose）")

    if absent_cands:
        print("=== config/known_absent.tsv への追記候補（恒久的に存在しないものだけ登録） ===")
        for c in absent_cands[:20]: print("  " + c)
        if len(absent_cands) > 20: print(f"  … 他 {len(absent_cands)-20}件")
    print(f"\n配信 {ok}本を認識（不足あり {warn}本）" + ("　※--dry-run のため書き込みなし" if a.dry_run else ""))
    if not a.dry_run:
        print("次: python scripts/s1_normalize.py --all")

if __name__ == "__main__":
    main()
