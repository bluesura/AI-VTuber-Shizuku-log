#!/usr/bin/env python3
"""deslop-ja check.py: 日本語文章のAI臭を機械的に検出する。

使い方:
    python3 check.py 文章.md              # 人間向けレポート
    python3 check.py 文章.md --json       # 機械可読
    cat 文章.md | python3 check.py        # 標準入力
    python3 check.py 文章.md --tech       # 技術文脈: 条件付き語（効く・強い・重い…）を報告しない
    python3 check.py 文章.md --paper      # 論文モード: 本稿・本研究・受動態は正当、リズム指標は情報扱い

依存パッケージなし（Python 3.8以上）。

検出は「疑い」であって命令ではない。固有名詞の反復、パターン名としての言及、
引用文などの誤検知は理由を付けて残す。検出ゼロを目的にしない。

文長の指標（burstiness、変動係数）と「〜ではなく」比率の閾値は、
coji/natural-japanese が公開した人間137本×AI406本の計測値
（burstiness 閾値 -0.24、「〜ではなく」比率 人間中央値1.5% / AI 8.3%）を
参考に、文字数ベースで緩めに置いている。モーラ数ではなく文字数で近似する。
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, asdict, field
from typing import Iterable

JA = r"[぀-ヿ一-鿿々〆ヵヶ]"  # ひらがな・カタカナ・漢字

# ---------------------------------------------------------------------------
# 語彙表（references/vocabulary.md の抜粋。増やすときは両方を更新する）
# ---------------------------------------------------------------------------

STOCK_PHRASES: list[tuple[str, str]] = [
    (r"本記事では|本稿では.{0,12}(述べ|解説|紹介)|ここでは.{0,12}解説|について解説します", "前置きの宣言"),
    (r"ご質問ありがとうございます|素晴らしい(ご)?質問", "チャットボットの残骸"),
    (r"近年.{0,14}(注目され|注目を集め)|急速に(普及|進展|拡大)し", "定型の冒頭"),
    (r"現代社会において|日々変化する現代", "定型の冒頭"),
    (r"多いはずだ|経験があるのではないでしょうか|方も多いでしょう|少なくありません|と思ったことはありませんか|をご存知でしょうか", "見せかけの共感・決めつけ開幕"),
    (r"結論から(言う|言え|申し上げる)と|先に結論を", "結論の宣言"),
    (r"以下の\d+つの(観点|ポイント|点)|[3３]つの観点|それぞれ順に見て|順を追って説明|以下で詳しく解説", "構造の宣言"),
    (r"ステップ\s?\d|STEP\s?\d|Step\s?\d", "ステップ表記"),
    (r"ここからが本題|ここで重要なのは|ここで注目すべき|率直に言えば|端的に言えば|正直に言うと|実はですね|結局のところ|あえて言うなら", "咳払いの前置き"),
    (r"驚くほど楽に|見え方が(大きく)?変わり|重要な前提から確認", "自己宣伝の枕詞"),
    (r"いかがでした(でしょう)?か|ぜひ参考に|ぜひ.{0,8}してみてください|ご参考になれば|お気軽に", "定型の締め"),
    (r"今後の展開が注目|今後のさらなる|さらなる(検討|研究|発展|議論)が(望まれ|期待され|必要)|が期待され(ます|る)。", "展望テンプレ"),
    (r"(^|\n)\s*(まとめると|以上より|以上のことから|総じて)", "結論の定型開始"),
    (r"重要性を再認識|避けて通れ(ません|ない)|鍵を握って", "定型句"),
    (r"にもかかわらず.{0,24}(重要|意義|示唆|有用)|Despite these limitations", "限界の後の救済文"),
    (r"あくまで(個人|一個人)の(経験|見解|感想)|環境によって異なる可能性", "免責の儀式"),
    (r"そのお気持ち|お察しします|その認識は.{0,6}正し|その理解で合って|非常に的確|(するどい|鋭い)(視点|指摘|ご指摘)|本質を突いて|素晴らしい着眼", "過剰共感・採点"),
    (r"おっしゃる通り|(^|\n)\s*確かに|(^|\n)\s*なるほど", "追従"),
    (r"ケースバイケース|場合によります|価値観によります|状況に応じて異なり|賛否が分かれ|メリットもあればデメリットも|それぞれの良さが", "結論回避"),
    (r"あまり推奨され|注意が必要です|望ましくないとされ|避けたほうが良いでしょう", "弱い否定"),
    (r"一概には言えません|賛否両論あります|もちろん例外はあります", "予防線"),
    (r"課題はあるものの.{0,20}(発展|成長|進化)", "テンプレ的な課題と展望"),
    (r"このとき確信した|ここで気づいた|の正体とは", "演出語"),
    (r"(良ければ|よければ|ご希望であれば|ご興味があれば).{0,30}(教えます|紹介します|まとめます|でき)|も(教え|でき)ますよ", "追加提案の押し付け"),
    (r"(^|\n)\s*重要なのは", "咳払いの前置き（重要なのは）"),
    (r"多くの(人|方|読者|エンジニア|研究者|企業)が", "一般化（誰の話か書く）"),
    (r"正面から(扱|見|書|立て|回収)", "正面から系（姿勢の宣言）"),
    (r"大きく分けて\d+つ|[3３]つの(理由|ポイント|要素)があ", "三点構成の圧力"),
    (r"(掘り下げ|言語化し|探求し|について見て)(ます|いき|てい)|今回は.{0,12}について(紹介|解説)し", "空虚な動詞・予告口調"),
    (r"それでは、|このような中|ここで注目したいのは|(紹介|解説|深掘り)していきます", "橋渡し語"),
    (r"個人差がありますが|あくまで一例ですが|とも限りません", "予防線"),
    (r"驚くべきことに|(^|\n)\s*実は", "演出（驚きの演出）"),
    (r"することが(重要|大切|不可欠)(です|である|だ)", "〜することが重要です"),
]

PAPER_PHRASES: list[tuple[str, str]] = [
    (r"興味深いことに|注目すべきことに|特筆すべきことに", "結果に解釈語（考察へ）"),
    (r"\b(interestingly|notably|importantly)\b", "結果に解釈語（考察へ）"),
    (r"\b(in summary|in conclusion)\b", "結論の定型開始"),
    (r"\bfurther (research|studies|investigation) (is|are) (needed|warranted)\b", "単独の結語"),
    (r"(重要|意義深い)な?示唆を(与え|含|提供)|makes? an important contribution|important insights", "自己評価"),
]

HEDGES = (
    r"と言えるでしょう|と言えるのではないでしょうか|とも言えるでしょう|ではないでしょうか|と考えられ(ます|る|ている)|"
    r"が挙げられ(ます|る)|ということが挙げられ|こと[がも]でき(ます|る)|こと[がも]可能(です|である|だ)|することが(大切|重要)だと|"
    r"望ましいでしょう|てみてはいかがでしょうか|が現実的です|たいところです|とされてい(ます|る)|と言われてい(ます|る)"
)

SENTENCE_START_CONNECTIVES = r"(さらに|また|加えて|そして|したがって|そのため|結果として|一方で|このように)[、,]?"

AI_WORDS: list[tuple[str, str]] = [
    # 意義づけ・評価語
    (r"浮き彫り", "評価語"), (r"重要(な|です|だ|である|なのは)", "評価語"), (r"重要性", "評価語"), (r"不可欠", "評価語"), (r"極めて", "評価語"),
    (r"意義深い", "評価語"), (r"示唆に富", "評価語"), (r"注目すべき|注目に値", "評価語"), (r"画期的", "評価語"), (r"革新的", "評価語"),
    (r"多面的|包括的|網羅的|多角的", "評価語"), (r"堅牢", "評価語"), (r"シームレス", "評価語"), (r"最適化", "評価語"), (r"透明性", "評価語"),
    (r"再定義", "評価語"), (r"重要な役割", "評価語"), (r"過言ではな", "評価語"), (r"に他ならな", "評価語"), (r"言うまでもな", "評価語"),
    (r"間違いなく|紛れもなく", "評価語"), (r"大きな意味を持|重大な意味を持", "評価語"), (r"本質的な問題|構造的な課題", "曖昧な断言"), (r"核心的|鍵となる|根本的な|総合的", "空虚な形容"), (r"様々な|多様な", "具体の省略"),
    # 質感・認知系
    (r"手触り", "偏愛語"), (r"泥臭", "偏愛語"), (r"肌感", "偏愛語"), (r"体温", "偏愛語"), (r"温度感", "偏愛語"), (r"熱量", "偏愛語"),
    (r"血の通った", "偏愛語"), (r"解像度", "偏愛語"), (r"腹落ち", "偏愛語"), (r"メンタルモデル", "偏愛語"), (r"地に足の", "偏愛語"),
    (r"等身大", "偏愛語"), (r"余白", "偏愛語"), (r"静かな(自信|強さ|反逆|真実|革命)", "偏愛語(quiet)"),
    # 抽象名詞
    (r"本質", "抽象名詞"), (r"営み", "抽象名詞"), (r"装置", "抽象名詞"), (r"思想", "抽象名詞"), (r"哲学", "抽象名詞"),
    (r"分水嶺", "抽象名詞"), (r"定点観測", "抽象名詞"), (r"深掘り", "抽象名詞(delve)"), (r"濃密", "偏愛語"), (r"落とし込(む|み|ん)", "ジャーゴン"),
    # 壮大化
    (r"真理", "壮大化"), (r"真実", "壮大化"), (r"結末", "壮大化"), (r"宿命", "壮大化"), (r"境地", "壮大化"), (r"極致|究極", "壮大化"),
    (r"虚飾", "壮大化"), (r"美学", "壮大化"), (r"重厚感", "壮大化"), (r"深淵", "壮大化"), (r"禁欲的", "壮大化"), (r"優美", "壮大化"),
    (r"残酷|冷徹|冷酷", "壮大化"), (r"凝縮|結晶", "壮大化"), (r"枯淡", "壮大化"),
    # 比喩テンプレ
    (r"羅針盤|道しるべ|灯台", "比喩テンプレ"), (r"架け橋", "比喩テンプレ"), (r"潤滑油", "比喩テンプレ"), (r"車の両輪", "比喩テンプレ"),
    (r"触媒|起爆剤", "比喩テンプレ"), (r"スパイス", "比喩テンプレ"), (r"土台", "比喩テンプレ"), (r"という旅", "比喩テンプレ"),
    # 一語断定（無条件）
    (r"つまずく|つまずき", "一語断定"), (r"切り分け", "一語断定"), (r"逃が(す|し)", "一語断定"), (r"目が滑", "一語断定(誤用注意)"),
    # 横文字メタファー・ジャーゴン
    (r"OSをアップデート|思考のOS", "横文字メタファー"), (r"ハックする|をハック", "横文字メタファー"), (r"習慣を.{0,4}インストール", "横文字メタファー"),
    (r"マインドを.{0,4}リファクタ", "横文字メタファー"), (r"ディープダイブ", "ジャーゴン"), (r"レバレッジ", "ジャーゴン"), (r"ピボット", "ジャーゴン"),
    (r"にコミットする", "ジャーゴン"), (r"ブラッシュアップ", "カタカナ語"), (r"ソリューション", "カタカナ語"), (r"イノベーション", "カタカナ語"),
    (r"パラダイムシフト", "カタカナ語"), (r"コンセンサス", "カタカナ語"), (r"コミットメント", "カタカナ語"), (r"レジリエンス", "カタカナ語"),
    (r"サステナブル", "カタカナ語"), (r"インサイト", "カタカナ語"), (r"エコシステム", "カタカナ語"), (r"シナジー", "カタカナ語"),
    (r"ブレークスルー", "カタカナ語"), (r"ポテンシャル", "カタカナ語"), (r"エンパワー", "カタカナ語"), (r"アライメント|アラインメント", "カタカナ語"),
    (r"インテグリティ", "カタカナ語"), (r"コラボレーション", "カタカナ語"), (r"インプリメンテーション", "カタカナ語"), (r"プライオリティ", "カタカナ語"),
    (r"ナレッジ", "カタカナ語"), (r"インパクト", "カタカナ語"),
    # 副詞スタッキング
    (r"めっちゃ|めちゃくちゃ", "副詞"), (r"ガチで", "副詞"), (r"マジで", "副詞"), (r"普通に", "副詞"), (r"かなり", "副詞"),
    (r"非常に", "副詞"), (r"本当に", "副詞"), (r"実に", "副詞"),
]

# 一般文の地の文で疑う語（--paper では報告しない）
PROSE_ONLY_WORDS: list[tuple[str, str]] = [
    (r"本稿", "アカデミック自称"), (r"本論考", "アカデミック自称"), (r"(^|[^著])筆者", "アカデミック自称"),
]

# 条件付き語: 技術文脈では通常語。比喩用法かどうかは人が判断する（情報レベルのみ）。
CONDITIONAL_WORDS: list[tuple[str, str]] = [
    (r"効(く|い|き)", "効く"), (r"強い", "強い"), (r"重い", "重い"), (r"通(る|った|り)", "通る"), (r"刺さ(る|っ)", "刺さる"),
    (r"粗い", "粗い"), (r"に落ち(る|た|て)", "〜に落ちる"), (r"整え(る|た|て)", "整える"), (r"レイヤー", "レイヤー"), (r"構造", "構造"),
    (r"非対称性", "非対称性"), (r"参謀", "参謀"), (r"トリガー", "トリガー"), (r"スタブ", "スタブ"), (r"カニバリ", "カニバリ"),
    (r"コンテキスト", "コンテキスト"), (r"フレームワーク", "フレームワーク"), (r"リソース", "リソース"), (r"アプローチ", "アプローチ"),
    (r"インフラ", "インフラ"), (r"接続", "接続"),
]

ENGLISH_WORDS = [
    "additionally", "align with", "bolstered", "crucial", "delve", "delves", "delving", "emphasizing", "enduring", "enhance",
    "enhances", "enhancing", "fostering", "garner", "highlight", "highlights", "highlighting", "interplay", "intricate", "intricacies",
    "landscape", "meticulous", "meticulously", "pivotal", "showcase", "showcases", "showcasing", "tapestry", "testament", "underscore",
    "underscores", "underscoring", "valuable", "vibrant", "leverage", "leverages", "leveraging", "comprehensive", "transformative",
    "streamline", "robust", "nuanced", "holistic", "seamless", "groundbreaking", "game-changer", "paradigm", "unprecedented", "elevate",
    "harness", "unlock", "unleash", "cutting-edge", "synergy", "empower", "stands as", "serves as", "marks a", "represents a",
    "not only", "evolving landscape", "indelible mark", "setting the stage", "plays a vital role", "plays a significant role",
    "it's worth noting", "it is worth noting", "in today's", "ever-evolving", "let's dive in", "great question",
]

# ---------------------------------------------------------------------------

@dataclass
class Finding:
    level: str          # 重大 / 警告 / 情報
    check: str
    message: str
    line: int | None = None
    snippet: str | None = None
    count: int | None = None


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add(self, level: str, check: str, message: str, line: int | None = None, snippet: str | None = None, count: int | None = None):
        self.findings.append(Finding(level, check, message, line, snippet, count))


# ---------------------------------------------------------------------------
# 前処理
# ---------------------------------------------------------------------------

def strip_code_blocks(lines: list[str]) -> list[tuple[int, str]]:
    """コードブロックを除いた (行番号, 行) のリスト。"""
    out = []
    in_code = False
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        out.append((i, line))
    return out


def is_prose_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith(("#", "|", ">", "```", "<!--")):
        return False
    if re.match(r"^\s*([-*・•]|\d+[.．)])\s", line):
        return False
    return True


SENT_SPLIT = re.compile(r"(?<=[。！？!?])\s*")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENT_SPLIT.split(text)]
    return [p for p in parts if len(p) >= 2]


def prose_paragraphs(numbered: list[tuple[int, str]]) -> list[list[str]]:
    """空行で区切った散文段落ごとの文リスト。見出し・箇条書き・引用・表は除く。"""
    paragraphs: list[list[str]] = []
    buf: list[str] = []
    for _, line in numbered:
        if not line.strip():
            if buf:
                paragraphs.append(split_sentences("".join(buf)))
                buf = []
            continue
        if is_prose_line(line):
            buf.append(line.strip())
        else:
            if buf:
                paragraphs.append(split_sentences("".join(buf)))
                buf = []
    if buf:
        paragraphs.append(split_sentences("".join(buf)))
    return [p for p in paragraphs if p]


def in_kagi(line: str, m: re.Match) -> bool:
    """マッチが同一行の「」内にあるか。パターン名としての言及や引用を誤検知しないための近似。"""
    before = line[: m.start()]
    after = line[m.end():]
    return before.rfind("「") > before.rfind("」") and "」" in after


def snippet_of(line: str, m: re.Match, width: int = 22) -> str:
    a = max(0, m.start() - width)
    b = min(len(line), m.end() + width)
    return ("…" if a > 0 else "") + line[a:b].strip() + ("…" if b < len(line) else "")


# ---------------------------------------------------------------------------
# 各チェック
# ---------------------------------------------------------------------------

def check_artifacts(numbered, rep: Report):
    dash = re.compile(r"[—–―─━]|――|──|——")
    bold_colon = re.compile(r"^\s*[-*・•]\s*\*\*[^*\n]*?(?:[:：]\s*\*\*|\*\*\s*[:：])")
    colon_space = re.compile(r"(：\s)|(" + JA + r":\s)")
    inner_space = re.compile(r"(?<=" + JA + r") (?=" + JA + r")")
    dq = re.compile(r"\"[^\"\n]*" + JA + r"[^\"\n]*\"")
    fw_slash = re.compile(JA + r"／" + JA)
    emoji_end = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2705]\s*$")
    num_heading = re.compile(r"^#+\s*\d+[.．]\s")
    for n, line in numbered:
        for m in dash.finditer(line):
            rep.add("重大", "全角ダッシュ", "全角ダッシュ／em dash。（）か読点に置き換える", n, snippet_of(line, m))
            break
        if bold_colon.search(line):
            rep.add("重大", "太字コロン箇条書き", "「**ラベル:** 内容」型。プレーンな箇条書きか散文にする", n, line.strip()[:60])
        if "**" in line and not bold_colon.search(line):
            rep.add("情報", "太字記号", "** が残っている。強調が要るか確認", n, line.strip()[:60])
        m = colon_space.search(line)
        if m:
            rep.add("警告", "コロン後の半角スペース", "英語の書式癖。コロンの後の半角スペースを削る", n, snippet_of(line, m))
        m = inner_space.search(line)
        if m:
            rep.add("情報", "日本語内の半角スペース", "全角文字に混じった半角スペース", n, snippet_of(line, m))
        m = dq.search(line)
        if m:
            rep.add("警告", "半角ダブルクォート", "日本語を \"\" で囲んでいる。「」にするか囲まない", n, snippet_of(line, m))
        m = fw_slash.search(line)
        if m:
            rep.add("情報", "全角スラッシュ並列", "概念を／で並べている。「や」「または」に戻せるか確認", n, snippet_of(line, m))
        if emoji_end.search(line):
            rep.add("情報", "段落末の絵文字", "段落末の装飾絵文字", n, line.strip()[-30:])
        if num_heading.match(line):
            rep.add("情報", "番号付き見出し", "見出しに「1.」を付けている", n, line.strip()[:40])
    # 「」の密度
    text = "\n".join(l for _, l in numbered)
    ja_chars = len(re.findall(JA, text))
    quotes = text.count("「")
    if ja_chars > 400 and quotes / max(ja_chars, 1) > 0.02:
        rep.add("情報", "カギ括弧の密度", f"「」が{quotes}回（{1000*quotes/ja_chars:.1f}/1000字）。形容詞や心情を囲んでいないか確認", count=quotes)


def check_phrases(numbered, rep: Report, paper: bool):
    table = list(STOCK_PHRASES) + (PAPER_PHRASES if paper else [])
    for pat, label in table:
        rx = re.compile(pat, re.IGNORECASE | re.MULTILINE)
        for n, line in numbered:
            m = rx.search(line)
            if m:
                if in_kagi(line, m):
                    rep.add("情報", f"定型句(引用内): {label}", "「」内。言及なら残す", n, snippet_of(line, m))
                else:
                    rep.add("警告", f"定型句: {label}", "削るか、本題から始める", n, snippet_of(line, m))


def check_hedges(numbered, rep: Report):
    rx = re.compile(HEDGES)
    hits = []
    for n, line in numbered:
        for m in rx.finditer(line):
            if not in_kagi(line, m):
                hits.append((n, snippet_of(line, m)))
    rep.stats["hedges"] = len(hits)
    if len(hits) >= 3:
        rep.add("警告", "断定回避の連発", f"「〜と言えるでしょう」「〜と考えられます」「〜することができます」型が{len(hits)}回。言い切るか削る", count=len(hits))
    for n, s in hits[:8]:
        rep.add("情報", "断定回避", "", n, s)


def check_connectives(numbered, rep: Report):
    kore = re.compile(r"これにより")
    start = re.compile(r"(^|[。！？!?]\s*)" + SENTENCE_START_CONNECTIVES)
    kore_hits, start_hits = [], []
    for n, line in numbered:
        for m in kore.finditer(line):
            if in_kagi(line, m):
                rep.add("情報", "これにより(引用内)", "「」内。言及なら残す", n, snippet_of(line, m))
            else:
                kore_hits.append((n, snippet_of(line, m)))
        for m in start.finditer(line):
            start_hits.append((n, m.group(2), snippet_of(line, m)))
    for n, s in kore_hits:
        rep.add("重大", "これにより", "日本語AI文章の最大マーカー。因果を書き直す", n, s)
    ippou = sum(len(re.findall(r"一方で", line)) for _, line in numbered)
    if ippou >= 2:
        rep.add("警告", "「一方で」の連発", f"{ippou}回。反対側を機械的に足していないか。要るときだけ「ただし」", count=ippou)
    rep.stats["sentence_start_connectives"] = len(start_hits)
    if len(start_hits) >= 3:
        words = ", ".join(sorted({w for _, w, _ in start_hits}))
        rep.add("警告", "文頭接続詞の連打", f"文頭の接続詞が{len(start_hits)}回（{words}）。順接は削れる", count=len(start_hits))
        for n, _, s in start_hits[:6]:
            rep.add("情報", "文頭接続詞", "", n, s)


def check_dewanaku(paragraphs, rep: Report):
    sents = [s for p in paragraphs for s in p]
    if len(sents) < 6:
        return
    rx = re.compile(r"ではなく|ではない[。！]|ではありません[。！]|じゃな(く|い[。！])|のみならず|だけでなく|単なる")
    hit = [s for s in sents if rx.search(s)]
    ratio = len(hit) / len(sents)
    rep.stats["dewanaku_ratio"] = round(ratio, 3)
    if ratio >= 0.10:
        rep.add("重大", "「〜ではなく」比率", f"{len(hit)}/{len(sents)}文（{100*ratio:.1f}%）。人間の中央値1.5%、AI 8.3%。Bだけ書く", count=len(hit))
    elif ratio >= 0.05:
        rep.add("警告", "「〜ではなく」比率", f"{len(hit)}/{len(sents)}文（{100*ratio:.1f}%）。人間の中央値は1.5%", count=len(hit))


def check_vocab(numbered, rep: Report, tech: bool, paper: bool):
    text = "\n".join(l for _, l in numbered)
    ja_chars = max(len(re.findall(JA, text)), 1)

    def scan(table, level_single, level_multi, tag):
        total = 0
        for pat, label in table:
            rx = re.compile(pat)
            ms = list(rx.finditer(text))
            if not ms:
                continue
            total += len(ms)
            first_line = text.count("\n", 0, ms[0].start()) + 1
            lvl = level_multi if len(ms) >= 2 else level_single
            rep.add(lvl, f"{tag}: {label}", f"「{ms[0].group(0)}」{len(ms)}回", first_line, None, len(ms))
        return total

    total = scan(AI_WORDS, "情報", "警告", "AI語")
    if not paper:
        total += scan(PROSE_ONLY_WORDS, "情報", "警告", "AI語")
    rep.stats["ai_words_per_1000"] = round(1000 * total / ja_chars, 2)
    if ja_chars >= 200 and total >= 3 and 1000 * total / ja_chars >= 3:
        rep.add("警告", "AI語の密度", f"AI語が{total}回（{1000*total/ja_chars:.1f}/1000字）。3/1000字以上は疑う", count=total)
    if not tech:
        scan(CONDITIONAL_WORDS, "情報", "情報", "条件付き語（比喩用法か確認）")

    # 英語
    hits = []
    for w in ENGLISH_WORDS:
        rx = re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE)
        n = len(rx.findall(text))
        if n:
            hits.append((w, n))
    if hits:
        rep.stats["english_ai_words"] = sum(n for _, n in hits)
        lvl = "警告" if sum(n for _, n in hits) >= 3 else "情報"
        rep.add(lvl, "英語AI語", ", ".join(f"{w}×{n}" for w, n in hits), count=sum(n for _, n in hits))


def check_rhythm(paragraphs, rep: Report, paper: bool):
    sents = [s for p in paragraphs for s in p]
    n = len(sents)
    rep.stats["sentences"] = n
    exclam = sum(1 for s_ in sents if s_.endswith(("！", "!")))
    if n >= 3 and exclam / n >= 0.5:
        rep.add("情報", "感嘆符の連打", f"{n}文中{exclam}文が「！」で終わる。熱量の演出になっていないか", count=exclam)
    if n < 8:
        return
    lens = [len(re.sub(r"\s", "", s)) for s in sents]
    mu = statistics.mean(lens)
    sd = statistics.pstdev(lens)
    cv = sd / mu if mu else 0
    burst = (sd - mu) / (sd + mu) if (sd + mu) else 0
    rep.stats.update({"sentence_len_mean": round(mu, 1), "sentence_len_sd": round(sd, 1), "sentence_len_cv": round(cv, 3), "burstiness": round(burst, 3)})
    level = "情報" if paper else "警告"
    if burst < -0.30:
        rep.add(level, "文長リズムの均質さ", f"burstiness={burst:.2f}（平均{mu:.0f}字, SD {sd:.0f}）。-0.30未満は文の長短のメリハリが乏しい。4文字の文と80文字の文を混ぜる", count=n)
    if cv < 0.30:
        rep.add(level, "文長の変動係数", f"CV={cv:.2f}。0.30未満は全文が似た長さ", count=n)

    # 段落の文数
    counts = [len(p) for p in paragraphs if len(p) >= 2]
    rep.stats["paragraph_sentence_counts"] = counts
    if len(counts) >= 3:
        most = max(set(counts), key=counts.count)
        share = counts.count(most) / len(counts)
        if share == 1.0:
            rep.add(level, "段落構造の均質さ", f"{len(counts)}段落すべてが{most}文。1行の段落と長い段落を混ぜる", count=len(counts))
        elif len(counts) >= 4 and share >= 0.75:
            rep.add("情報", "段落構造の均質さ", f"{len(counts)}段落中{counts.count(most)}段落が{most}文", count=len(counts))

    # 体言止め（漢字・カタカナで終わる文を近似）
    if not paper and n >= 15:
        taigen = [s for s in sents if re.search(r"[一-鿿々ァ-ヺー][。！？!?]?$", s)]
        rep.stats["taigen_dome"] = len(taigen)
        if not taigen:
            rep.add("情報", "体言止めゼロ", f"{n}文中0。随筆では人間の書き手の60%が使い、AIは0%。少し混ぜる", count=0)
        elif len(taigen) / n > 0.20:
            rep.add("情報", "体言止めの過用", f"{n}文中{len(taigen)}文（{100*len(taigen)/n:.0f}%）。20%を超えると読み手が疲れる", count=len(taigen))

    # 文末の固定
    ends = [re.sub(r"[。！？!?]$", "", s)[-2:] for s in sents]
    run, best, best_end = 1, 1, ends[0]
    for i in range(1, len(ends)):
        if ends[i] == ends[i - 1]:
            run += 1
            if run > best:
                best, best_end = run, ends[i]
        else:
            run = 1
    rep.stats["max_same_ending_run"] = best
    if best >= 5:
        rep.add("警告", "文末の固定", f"「{best_end}」で終わる文が{best}回連続。語尾を混ぜる", count=best)
    polite = sum(1 for e in ends if e in ("です", "ます", "した", "せん"))
    if n >= 10 and polite / n >= 0.85:
        rep.add("情報", "文末パターン", f"{n}文中{polite}文が「です／ます／した」で終わる", count=polite)



# ---------------------------------------------------------------------------

ORDER = {"重大": 0, "警告": 1, "情報": 2}


def check_reading_load(paragraphs, rep: Report):
    """読みやすさの読解負荷（natural-japanese の --reading-load を依存なしで近似）。全て情報レベル。"""
    sents = [s_ for p in paragraphs for s_ in p]
    kanji_run = re.compile(r"[一-鿿々]{7,}")
    no_chain = re.compile(r"の[^、。「」（）]{1,10}の[^、。「」（）]{1,10}の")
    double_neg = re.compile(r"(ない|なかった|なく)(わけ|こと|とは限ら|とも言え|もな)(では|じゃ|は|)?な")
    ga_chain = re.compile(r"[^、。]{3,}が、[^、。]{3,}が、")
    for s_ in sents:
        n = len(re.sub(r"\s", "", s_))
        if n > 110:
            rep.add("情報", "読解負荷 B1 一文が長い", f"{n}字。一文一義に分ける", None, s_[:40] + "…")
        elif n > 90:
            rep.add("情報", "読解負荷 B1 一文がやや長い", f"{n}字（目安90字）", None, s_[:40] + "…")
        for m in kanji_run.finditer(s_):
            rep.add("情報", "読解負荷 C1 漢字の連続", f"「{m.group(0)}」{len(m.group(0))}字。助詞や訓読みを挟む", None, None)
        if no_chain.search(s_):
            rep.add("情報", "読解負荷 C2 「の」の連鎖", "3連以上。動詞に戻すか文を分ける", None, s_[:40] + "…")
        if double_neg.search(s_):
            rep.add("情報", "読解負荷 A1 二重否定", "肯定に直す", None, s_[:40] + "…")
        if ga_chain.search(s_):
            rep.add("情報", "読解負荷 B6 「が、」の連鎖", "逆接でない「が」を「。」に", None, s_[:40] + "…")
        commas = s_.count("、")
        if (commas >= 3 and n >= 80) or (commas >= 4 and n >= 50):
            rep.add("情報", "読解負荷 F1 埋もれた列挙", f"読点{commas}個・{n}字。箇条書きか文分割に", None, s_[:40] + "…")


def diff_baseline(rep: Report, baseline_path: str, name: str):
    """前回の --json 出力と比べて 解消/新規/継続 を stats に入れる。"""
    try:
        prev = json.load(open(baseline_path, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        rep.stats["baseline_error"] = str(e)
        return
    prev_items = []
    for entry in prev if isinstance(prev, list) else [prev]:
        if isinstance(entry, dict) and (entry.get("file") == name or len(prev) == 1):
            prev_items = entry.get("findings", [])
    key = lambda f: (f["check"], (f.get("snippet") or f.get("message") or "")[:24])  # noqa: E731
    prev_keys = {key(f) for f in prev_items}
    cur_keys = {key(asdict(f)) for f in rep.findings}
    rep.stats["baseline"] = {
        "解消": len(prev_keys - cur_keys),
        "新規": len(cur_keys - prev_keys),
        "継続": len(cur_keys & prev_keys),
    }


def run(text: str, tech: bool, paper: bool, reading_load: bool = False) -> Report:
    rep = Report()
    lines = text.splitlines()
    numbered = strip_code_blocks(lines)
    paragraphs = prose_paragraphs(numbered)
    rep.stats["mode"] = "paper" if paper else ("tech" if tech else "general")
    check_artifacts(numbered, rep)
    check_phrases(numbered, rep, paper)
    check_hedges(numbered, rep)
    check_connectives(numbered, rep)
    check_dewanaku(paragraphs, rep)
    check_vocab(numbered, rep, tech, paper)
    check_rhythm(paragraphs, rep, paper)
    if reading_load:
        check_reading_load(paragraphs, rep)
    rep.findings.sort(key=lambda f: (ORDER[f.level], f.line or 0))
    return rep


def render(rep: Report, name: str) -> str:
    out = [f"== {name} =="]
    counts = {k: 0 for k in ORDER}
    for f in rep.findings:
        counts[f.level] += 1
    out.append("重大 {重大} / 警告 {警告} / 情報 {情報}".format(**counts))
    if "baseline" in rep.stats:
        b = rep.stats["baseline"]
        out.append(f"前回比: 解消 {b['解消']} / 新規 {b['新規']} / 継続 {b['継続']}")
    s = rep.stats
    if "sentences" in s:
        out.append(
            f"文数 {s['sentences']}, 平均文長 {s.get('sentence_len_mean', '-')}字, CV {s.get('sentence_len_cv', '-')}, "
            f"burstiness {s.get('burstiness', '-')}, 段落文数 {s.get('paragraph_sentence_counts', [])}, "
            f"「ではなく」比率 {s.get('dewanaku_ratio', '-')}, AI語 {s.get('ai_words_per_1000', 0)}/1000字"
        )
    out.append("")
    for f in rep.findings:
        loc = f"L{f.line} " if f.line else ""
        msg = f" {f.message}" if f.message else ""
        snip = f"  ┃ {f.snippet}" if f.snippet else ""
        out.append(f"[{f.level}] {loc}{f.check}{msg}{snip}")
    if not rep.findings:
        out.append("検出なし。")
    return "\n".join(out)


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="日本語文章のAI臭を検出する")
    ap.add_argument("files", nargs="*", help="対象ファイル（省略時は標準入力）")
    ap.add_argument("--json", action="store_true", help="JSONで出力")
    ap.add_argument("--tech", action="store_true", help="技術文脈: 条件付き語を報告しない")
    ap.add_argument("--paper", action="store_true", help="論文モード")
    ap.add_argument("--reading-load", action="store_true", help="読みやすさの読解負荷（一文の長さ、漢字連続、「の」連鎖、二重否定、埋もれた列挙）を情報レベルで指さす")
    ap.add_argument("--baseline", help="前回の --json 出力ファイル。解消/新規/継続を表示する")
    args = ap.parse_args(argv)

    sources: list[tuple[str, str]] = []
    if args.files:
        for path in args.files:
            with open(path, encoding="utf-8") as fh:
                sources.append((path, fh.read()))
    else:
        sources.append(("stdin", sys.stdin.read()))

    results = []
    for name, text in sources:
        rep = run(text, args.tech, args.paper, args.reading_load)
        if args.baseline:
            diff_baseline(rep, args.baseline, name)
        results.append((name, rep))

    if args.json:
        payload = [{"file": name, "stats": rep.stats, "findings": [asdict(f) for f in rep.findings]} for name, rep in results]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(render(rep, name) for name, rep in results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
