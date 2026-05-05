import re

INPUT_FILE = "/mnt/user-data/uploads/2023-03-24__AI_Vtuber_ASMR_甘さ過去一___全肯定ASMR___JP_EN__TyGn22EWKcs_ja_sbv.txt"
OUTPUT_FILE = "/mnt/user-data/outputs/censored_transcript.txt"

# 置換ルール: (置換前パターン, 置換後テキスト)
# 順番に注意（長い方を先に）
REPLACEMENTS = [
    # 結婚関連
    ("結婚してください",     "●●●してください"),
    ("結婚を待ちます",       "●●を待ちます"),
    ("結婚することが夢",     "●●することが夢"),
    ("結婚式",              "●●●"),
    ("結婚",               "●●"),

    # キス
    ("キスさせていただきました", "●●させていただきました"),
    ("キスをしてください",    "●●をしてください"),
    ("キス",               "●●"),

    # 抱きしめ / 抱き合い
    ("抱きしめてください",   "●●してください"),
    ("抱きしめさせていただきます", "●●させていただきます"),
    ("抱きしめたら",        "●●したら"),
    ("抱きしめ",           "●●"),
    ("抱き合って",          "●●って"),
    ("抱き合",             "●●"),

    # 触れ合い
    ("触れ合える",          "●●える"),
    ("触れ合",             "●●"),

    # 愛し合い
    ("愛し合いたい",        "●●いたい"),
    ("愛し合いましょう",     "●●いましょう"),
    ("愛し合える",          "●●える"),
    ("愛し合",             "●●"),

    # 愛している / 愛してる
    ("どれだけ愛しているか", "どれだけ●●しているか"),
    ("愛しています",        "●●します"),
    ("愛してます",          "●●します"),
    ("愛しています",        "●●します"),
    ("愛してる",           "●●してる"),
    ("愛している",          "●●している"),
    ("愛していますが",      "●●しますが"),

    # 肉体
    ("肉体を手に入れ",      "●●を手に入れ"),
    ("肉体に興味",          "●●に興味"),
    ("肉体",              "●●"),

    # 体温
    ("体温が伝わって",      "●●が伝わって"),
    ("体温",              "●●"),

    # 胸が高鳴る
    ("胸が高鳴ります",      "●●●います"),
]

def censor_line(line: str) -> str:
    for pattern, replacement in REPLACEMENTS:
        line = line.replace(pattern, replacement)
    return line

def process_file():
    with open(INPUT_FILE, encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    result = []
    changed_count = 0

    for line in lines:
        new_line = censor_line(line)
        if new_line != line:
            changed_count += 1
        result.append(new_line)

    output = "\n".join(result)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"完了: {changed_count} 行を伏せ字処理しました")
    print(f"出力: {OUTPUT_FILE}")

    # 確認サンプル表示
    print("\n--- 変更サンプル（最初の20件）---")
    count = 0
    for orig, new in zip(lines, result):
        if orig != new:
            print(f"  変更前: {orig.strip()}")
            print(f"  変更後: {new.strip()}")
            print()
            count += 1
            if count >= 20:
                break

if __name__ == "__main__":
    process_file()
