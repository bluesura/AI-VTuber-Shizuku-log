"""再生成可能なキャッシュを列挙し、明示指定時だけ削除する。"""
import argparse
import hashlib
import json
import re
import stat
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from file_state import file_lock

CACHE_DIRS = ("tools/scripts", "tools/shizuku-pipeline/scripts", "tools/skills/shizuku-wiki/scripts")
STAGING = ("shizuku-transcribe", "shizuku-nemotron-comparison", "shizuku-qwen-comparison")
MEDIA = re.compile(r"audio\.wav|source\.(?:mkv|mp4|webm|mov|flv|3gp)", re.I)


def safe(root, path):
    """通常のパスだけを許可。Windowsのジャンクションも再解析点として拒否する。"""
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"リンク・再解析点を参照するため対象外: {current}")
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError(f"対象がリポジトリ外です: {path}")
    return info


def python_caches(root, before):
    for relative in CACHE_DIRS:
        for path in (root / relative).rglob("__pycache__/*.pyc"):
            info = safe(root, path)
            if stat.S_ISREG(info.st_mode) and info.st_mtime <= before:
                yield path, info.st_size, "Pythonが再生成するバイトコード"


def run_media(root, run):
    safe(root, run)
    receipt = run / "cleanup-receipt.json"
    safe(root, receipt)
    data = json.loads(receipt.read_text(encoding="utf-8"))
    vid = data["video_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) or not run.name.startswith(f"run_{vid}_"):
        raise ValueError(f"実行記録の動画IDが一致しません: {run}")
    output = root / data["output"]
    if (not output.resolve().is_relative_to(root / "logs/youtube")
            or not re.fullmatch(re.escape(vid) + r"\.(?:transcribe|nemotron-3\.5-transcribe|qwen3-asr-1\.7b)\.txt", output.name)):
        raise ValueError(f"保存先が文字起こしログではありません: {output}")
    safe(root, output)
    if hashlib.sha256(output.read_bytes()).hexdigest() != data["sha256"]:
        raise ValueError(f"保存後に文字起こしが変わったため対象外: {output}")
    for name in data["files"]:
        if not MEDIA.fullmatch(name):
            raise ValueError(f"整理記録に対象外の名前があります: {name}")
        path = run / name
        if not path.exists() and not path.is_symlink():
            continue
        info = safe(root, path)
        if not stat.S_ISREG(info.st_mode) or info.st_mtime_ns > receipt.stat().st_mtime_ns:
            raise ValueError(f"完了記録より新しい、または通常ファイルではありません: {path}")
        yield path, info.st_size, "保存済みASRのハッシュを確認した再取得可能な動画・音声"


def report(root, candidates, execute):
    for path, size, reason in candidates:
        print(f"{path.relative_to(root)}\t{size} bytes\t{reason}")
        if execute:
            safe(root, path)
            path.unlink()
    return len(candidates)


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="既定。候補だけを表示")
    mode.add_argument("--execute", action="store_true", help="確認した候補を削除する")
    cli.add_argument("--older-days", type=int, default=7, help="Pythonキャッシュの最低経過日数")
    cli.add_argument("--run", type=Path, help="保存と内容を確認済みのASR実行フォルダ")
    args = cli.parse_args(argv)
    root = ROOT.resolve()
    if args.older_days < 0:
        cli.error("--older-days は0以上を指定してください。")
    try:
        if args.run:
            run = args.run.absolute()
            if run.parent not in {root / "outputs" / folder for folder in STAGING}:
                raise ValueError("outputs配下のASR専用実行フォルダを指定してください。")
            safe(root, run)
            if args.execute:
                with file_lock(run.parent / f".{run.name}.lock"):
                    count = report(root, list(run_media(root, run)), True)
            else:
                count = report(root, list(run_media(root, run)), False)
        else:
            before = time.time() - args.older_days * 86400
            count = report(root, list(python_caches(root, before)), args.execute)
        print(f"{'削除' if args.execute else '削除候補'} {count}件")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        cli.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
