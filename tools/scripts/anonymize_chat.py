import os
import re
import hashlib
import sys
from pathlib import Path

# 1. 定数
SALT = "shizuku_archive_secret_salt_2026"
TARGET_DIR = "../../logs/youtube"
WHITELIST = {"Aki", "aki5503", "Shizuku_AItuber", "Shizuku", "しずく", "あき先生"}

# 2. 補助関数 (hash_username)
def hash_username(username: str) -> str:
    """ユーザー名を一方向ハッシュ化し、個人の連続性を保ちつつ匿名化する"""
    username = username.strip()
    if username in WHITELIST:
        return username
    data = username + SALT
    h = hashlib.sha256(data.encode('utf-8')).hexdigest()
    return f"User_{h[:8]}"

# 3. 処理関数 (live_chat)
def anonymize_live_chat(filepath: Path):
    """ .live_chat.txt を読み込み、ユーザー名をハッシュ化して上書き保存する """
    with filepath.open('r', encoding='utf-8') as f:
        lines = f.readlines()
    pattern = re.compile(r'^(\[[-]?\d+:\d+(?::\d+)?\])\s*@([^:]+):\s*(.*)$')
    new_lines = []
    changed = False
    for line in lines:
        m = pattern.match(line)
        if m:
            timestamp, username, message = m.group(1), m.group(2).strip(), m.group(3)
            if username.startswith("User_") and len(username) == 13:
                new_lines.append(line)
                continue
            new_username = hash_username(username)
            new_lines.append(f"{timestamp} @{new_username}: {message}\n")
            changed = True
        else:
            new_lines.append(line)
    if changed:
        with filepath.open('w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"  ✅ ライブチャット匿名化: {filepath.name}")

# 4. 処理関数 (comments)
def anonymize_comments(filepath: Path):
    """ .comments.txt を読み込み、ユーザー名をハッシュ化して上書き保存する """
    with filepath.open('r', encoding='utf-8') as f:
        lines = f.readlines()
    pattern = re.compile(r'^(\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}\sUTC\])\s*@([^（\n]+)(.*)$')
    new_lines = []
    changed = False
    for line in lines:
        m = pattern.match(line)
        if m:
            timestamp, username, rest = m.group(1), m.group(2).strip(), m.group(3)
            if username.startswith("User_") and len(username) == 13:
                new_lines.append(line)
                continue
            new_username = hash_username(username)
            new_lines.append(f"{timestamp} @{new_username}{rest}\n")
            changed = True
        else:
            new_lines.append(line)
    if changed:
        with filepath.open('w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"  ✅ 通常コメント匿名化: {filepath.name}")

# 5. メインロジック（最後に置く）
def main():
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1])
        if target_path.is_file():
            print(f"🔍 個別ファイル処理開始: {target_path.resolve()}")
            # ここで呼び出すとき、既に関数は上に定義されているのでエラーになりません
            if target_path.name.endswith(".live_chat.txt"):
                anonymize_live_chat(target_path)
            elif target_path.name.endswith(".comments.txt"):
                anonymize_comments(target_path)
            else:
                print("  ⚠️ 警告: 対応していないファイル形式です。")
            return

    # 一括処理モード
    target_path = Path(TARGET_DIR)
    if not target_path.exists():
        target_path = Path(".")
    print(f"🔍 検索開始: {target_path.resolve()}")
    chat_files = list(target_path.rglob("*.live_chat.txt"))
    comment_files = list(target_path.rglob("*.comments.txt"))
    for cf in chat_files: anonymize_live_chat(cf)
    for cf in comment_files: anonymize_comments(cf)
    print("🎉 完了しました！")

if __name__ == "__main__":
    main()