# -*- coding: utf-8 -*-
"""shizuku-pipeline 共通ライブラリ（標準ライブラリのみ・追加インストール不要）"""
import json, re, hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE    = Path(__file__).resolve().parents[1]
DATA    = BASE / "data"
CONF    = BASE / "config"
PROMPTS = BASE / "prompts"
JST     = timezone(timedelta(hours=9))
NOISE_RE = re.compile(r"\[(?:音楽|拍手|笑い|Music|Applause)\]")
SENT_END = "。！？!?"

# ---------- 基本I/O ----------
def read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")

def write(path, text):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def jsonl_read(path):
    path = Path(path)
    if not path.exists(): return []
    out = []
    for i, line in enumerate(read(path).splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("```"): continue
        try:
            out.append(json.loads(line))
        except Exception as e:
            print(f"  ! {path.name}:{i} JSON解析失敗: {e}")
    return out

def jsonl_write(path, objs):
    write(path, "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in objs))

def jsonl_append(path, objs):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for o in objs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

def load_state(name, default):
    p = DATA / "state" / name
    if p.exists():
        try: return json.loads(read(p))
        except Exception: return default
    return default

def save_state(name, obj):
    write(DATA / "state" / name, json.dumps(obj, ensure_ascii=False, indent=1))

# ---------- 時刻 ----------
def mmss(t):
    t = int(t)
    if t < 0: return "-" + mmss(-t)
    if t >= 3600: return f"{t//3600}:{(t%3600)//60:02d}:{t%60:02d}"
    return f"{t//60}:{t%60:02d}"

def utc_to_jst(iso):
    """'2026-05-19T15:25:00.000Z' -> (date_jst, time_jst, date_utc)"""
    iso = iso.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso).astimezone(JST)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"), iso[:10]

def jdate(d):  # '2026-03-09' -> '2026年3月9日'（スキル§3-1: 地の文はゼロ埋めなし）
    y, m, dd = d.split("-")
    return f"{y}年{int(m)}月{int(dd)}日"

# ---------- パーサ ----------
def parse_sbv(path):
    """SBV -> [(t_sec, text)]（ブロック単位・生テキスト）"""
    raw = read(path).replace("\r\n", "\n")
    out = []
    for chunk in raw.strip().split("\n\n"):
        lines = chunk.split("\n")
        m = re.match(r"^(\d+):(\d+):(\d+)\.", lines[0])
        if m:
            t = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))
            out.append((t, "".join(lines[1:])))
    return out

def parse_chat(path):
    """live_chat -> [(t_sec, user, text)]（負時刻=配信開始前）"""
    msgs = []
    for line in read(path).splitlines():
        m = re.match(r"^\[(-?)(?:(\d+):)?(\d+):(\d+)\]\s+(@\S+?):\s?(.*)", line)
        if m:
            neg, h, mi, s, u, tx = m.groups()
            t = (int(h or 0)*3600 + int(mi)*60 + int(s)) * (-1 if neg else 1)
            msgs.append((t, u, tx))
    return msgs

def parse_info(path):
    txt = read(path).replace("\r\n", "\n")
    def g(label):
        m = re.search(rf"^{label}\s*[:：]\s*(.+)$", txt, re.M)
        return m.group(1).strip() if m else ""
    meta = {"title": g("タイトル"), "date": g("投稿日"), "video_id": g("動画ID"), "url": g("URL")}
    m = re.search(r"【説明】.*?\n[─-]+\n(.*)$", txt, re.S)
    meta["description"] = m.group(1).strip() if m else ""
    return meta

def parse_comments(path):
    """comments -> [{'header','text','ts_refs':[sec,...]}]"""
    if not Path(path).exists(): return []
    txt = read(path).replace("\r\n", "\n")
    entries, cur = [], None
    for line in txt.split("\n"):
        if line.startswith("# "): continue
        if re.match(r"^\[\d{4}-\d{2}-\d{2}", line):
            if cur: entries.append(cur)
            cur = {"header": line.strip(), "text": "", "ts_refs": []}
        elif cur is not None:
            cur["text"] += (line + "\n")
    if cur: entries.append(cur)
    for e in entries:
        e["text"] = e["text"].strip()
        for m in re.finditer(r"(?<![\d:])(?:(\d{1,2}):)?(\d{1,2}):([0-5]\d)(?![\d])", e["text"]):
            h, mi, s = m.groups()
            e["ts_refs"].append((int(h or 0))*3600 + int(mi)*60 + int(s))
    return entries

# ---------- 正規化 ----------
def load_fixes():
    fixes = []
    p = CONF / "asr_fixes.tsv"
    if p.exists():
        for line in read(p).splitlines():
            if line.startswith("#") or not line.strip(): continue
            cols = line.split("\t")
            if len(cols) >= 2: fixes.append((cols[0], cols[1]))
    return fixes

def apply_fixes(text, fixes):
    n = 0
    for wrong, right in fixes:
        c = text.count(wrong)
        if c:
            text = text.replace(wrong, right); n += c
    return text, n

def rejoin_sentences(blocks):
    """ブロック列 -> [(t_sec, 文)]。[音楽]等を除去し句点で再結合。tは文の先頭文字が属したブロックの開始秒。"""
    chars = []
    for t, txt in blocks:
        for ch in NOISE_RE.sub("", txt):
            chars.append((ch, t))
    sents, cur, cur_t = [], [], None
    for ch, t in chars:
        if cur_t is None: cur_t = t
        cur.append(ch)
        if ch in SENT_END:
            s = "".join(cur).strip()
            if s: sents.append((cur_t, s))
            cur, cur_t = [], None
    if cur:
        s = "".join(cur).strip()
        if s: sents.append((cur_t, s))
    return sents

def load_lexicon():
    fams = []
    p = CONF / "lexicon.tsv"
    if p.exists():
        for line in read(p).splitlines():
            if line.startswith("#") or not line.strip(): continue
            cols = line.split("\t")
            if len(cols) >= 2:
                fams.append((cols[0], [k for k in cols[1].split(",") if k]))
    return fams

# ---------- その他 ----------
def tokenize(text):
    """日本語の内容語らしき塊を取り出す（照合の前段フィルタ用）"""
    return set(re.findall(r"[一-龥]{2,}|[ァ-ヴー]{2,}|[A-Za-z]{3,}", text or ""))

def sha8(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]

def yt_url(vid, t):
    return f"https://www.youtube.com/live/{vid}?t={int(t)}"

def stream_dirs():
    root = DATA / "raw" / "streams"
    return sorted([d for d in root.iterdir() if d.is_dir()]) if root.exists() else []

def stream_meta(vid):
    p = DATA / "normalized" / "streams" / vid / "meta.json"
    return json.loads(read(p)) if p.exists() else {}

def all_card_files():
    return sorted((DATA / "cards").glob("*.jsonl"))

def load_all_cards():
    """{id: card} と {file: [cards]} を返す"""
    by_id, by_file = {}, {}
    for f in all_card_files():
        cards = jsonl_read(f)
        by_file[f] = cards
        for c in cards:
            by_id[c.get("id")] = c
    return by_id, by_file

def save_cards(by_file):
    for f, cards in by_file.items():
        jsonl_write(f, cards)

def find_stream(key):
    """vid か ディレクトリ名（date_vid）で raw/streams のディレクトリを引く"""
    for d in stream_dirs():
        if d.name == key or d.name.endswith("_" + key):
            return d
    return None
