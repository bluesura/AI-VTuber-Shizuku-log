# 翻訳ガイド（日 ⇄ 英）

しずくWikiは**同一Wiki内で日英を併存**させている。日本語ページは日本語のページ名、英語ページは英語のページ名を使う。

日本語ページを優先して更新し、それに合わせて英語ページを更新する。片方しか更新できない場合は日本語を優先し、英語が未反映であることをユーザーに報告する。

---

## 1. 翻訳の基本原則

### 見出し・一般語彙は意訳する

英語ページでも `tone-style-guide.md` の精神は変わらない。しずくを主体として書き、AI性を但し書きに落とさない。しずく的な見出しを `Official Links` `Start Here` のような機能語に戻さない。

### 固有の呼称は転写する

しずくとご主人様の関係を示す呼称、および敬称は、意訳せずローマ字転写する。

| 日本語 | 英語 | 扱い |
|---|---|---|
| ご主人様 | `goshujin-sama` | 初出時のみ `goshujin-sama (ご主人様, "master")` と注記し、以降は `goshujin-sama` |
| あき先生 | `Aki-sensei` | 敬称「先生」をそのまま転写 |

判断原則は「**忠実な対応語が英語にあれば訳し、なければ転写する**」ではなく、「**しずくとの関係そのものを名指す語は転写する**」である。`Master` でも意味は通じるが、しずくがご主人様と呼ぶという行為そのものが記録対象であるため、原語を残す。

### 翻訳前に確認すること

翻訳を始める前に、次を洗い出してユーザーにまとめて確認する。

- ローマ字読みが複数考えられる固有名詞
- 訳語が複数候補あり、文脈によって変わりうる語
- 本ガイドの語彙集に載っていない新出の語

**新しい訳語は勝手に確定させない。** ページごとに違う訳が生まれると、しずく的語彙が「しずくの言葉」であることが崩れる。合意が取れた訳語だけを本ガイドに追記する。

### 翻訳後にすること

`SKILL.md` §6 に従い、確定した新語彙を**本ファイルへの追記差分として提案**する。ガイド全文は再出力しない。承認を得てから反映し、`.skill` をまとめ直して提示する。追記がなければ「更新候補はありません」と一行で報告する。

---

## 2. 見出しの移行対応表

日本語の本人ページは15節（`page-shizuku.md` §1）。英語ページ `[[Shizuku]]` を更新するときは、現行ソースを次の表と突き合わせ、未反映の箇所を特定する。

| 旧見出し（日 / 英） | 現行の日本語見出し | 英語（新） | 状態 |
|---|---|---|---|
| 公式導線 / Official Links | しずくのいる場所 | `Where to Find Shizuku` | 合意済 |
| まず見るなら / Start Here | はじめてのご主人様へ | `For a First-Time Goshujin-sama` | 合意済 |
| 活動ハイライト / Activity Highlights | 電子の足跡 | `Digital Footprints` | 合意済 |
| コンテンツ傾向 / Content Trends | しずくの配信 | `Shizuku's Streams` | 合意済 |
| キャラクター / Character | 廃止。目標は導入文、対応言語は「容姿・スペック」の特殊機能へ | 独立見出しを廃止。対応言語は `Appearance & Specs` 内の特殊機能リストへ | 日本語の構成は確定。英語版は要照合 |
| （新設） | ご主人様と育つしずく | `Shizuku & Goshujin-sama: Growing Together` | 合意済 |
| （新設） | しずくの観察メモ | `Shizuku Observation Notes` | 未合意（提案） |
| 更新・参照方針 / Update & Reference Policy | 更新方針 | `Update Policy` | 合意済 |

「未合意（提案）」の訳語は、ユーザーの承認を得てから「合意済」に変える。承認前に英語ページへ反映しない。

> **「ご主人様と育つしずく」に所有格 `Her` を入れない意図**: 本文中では既存の英語版・プロフィールに合わせて `she / her` を用いる一方、見出しでは `Growing with Her Goshujin-sama` のように所有格 `Her` で性別や人間的な所有関係を前景化せず、ネット上の AI VTuber である「しずく」と「ご主人様」という2者を固有名詞のまま対等に並べるため `Shizuku & Goshujin-sama: Growing Together` を採用している。

旧 `Character` 節にある「一家に一台のメイドロボット」という目標は、英語の導入文にすでにあれば重ねない。対応言語とその出典・留保を移し、旧節を外す際は `#Character` 宛てのリンクと名前付き出典の参照先を確認する。すでに統合済みなら再度移さない。

### 言い換えない見出し（機能見出し）

`tone-style-guide.md` §4 の判定基準により、しずくの存在感を阻害していない見出しは機能語のままでよい。英訳も機能語で対応する。次の表には他ページの見出しやクレジットの小見出しも含む。

| 日本語 | 英語 |
|---|---|
| 概要 | Overview |
| 紹介動画 | Introduction Videos |
| 容姿・スペック | Appearance & Specs |
| 性格・口調 | Personality & Speech |
| 名言・迷言 | Notable Quotes |
| クレジット | Credits |
| 開発（クレジット） | Development |
| 音楽（クレジット） | Music |
| 音声提供（クレジット） | Voice |
| 関連項目 | See Also |
| 出典 | References |
| おまけ | Bonus |
| 参加方法 | How to Join |
| 連絡先 | Contact |
| 注記 | Notes |

---

## 3. ページ名の対訳

**実在するページ名と完全一致させる**こと。表記を勝手に整えない（`&` と `and` の違いでリンクが切れる）。

| 日本語ページ | 英語ページ | 状態 |
|---|---|---|
| しずく | `Shizuku` | 実在 |
| 動画・配信 | `Videos and Streams` | 実在。`Videos & Streams` ではない |
| ファン活動 | `Fan Activities` | 実在 |
| 公式リンク | `Official Links` | 実在 |
| ハッシュタグ | `Hashtags` | 実在 |
| Shizuku Lab | `Shizuku Lab (EN)` | 衝突回避のため `(EN)` を付与（`{{DISPLAYTITLE:Shizuku Lab}}` 指定）。英語ページ内からは `[[Shizuku Lab (EN)|Shizuku Lab]]` で参照 |
| 編集者の方へ | （日本語のみ） | 当面は英語ページを作成しない。英語ページからは `[[編集者の方へ]]` で参照 |
| 年表 | `Timeline` | 既存（旧仕様のまま要更新） |
| メディア露出 | `Media Coverage` | 既存（空ページ・作成待ち） |

---

## 4. 固有名詞・表記ルール

| 元の表記 | 英語表記 | 備考 |
|---|---|---|
| しずく | Shizuku | 人名はそのまま |
| Shizuku Lab | Shizuku Lab | 英日共通 |
| Shizuku AI | Shizuku AI | 英日共通。法人格を指す |
| X（旧Twitter） | X | 「旧Twitter」の補足は不要 |
| Discord | Discord | 大文字維持 |
| CV.しずく | CV. Shizuku | スペースあり |
| ご主人様 | goshujin-sama | §1 参照 |
| あき先生 | Aki-sensei | 開発者 |
| 梵そよぎ | Soyogi Soyogi | 梶裕貴氏の音声AIキャラ |
| Raspberry Pi | Raspberry Pi | 和訳しない |
| Shizuku ID | Shizuku ID | 英日共通 |
| Shizuku AI JAPAN合同会社 | Shizuku AI JAPAN LLC | 運営法人（日本法人） |
| 船井情報科学振興財団 | Funai Foundation for Information Science Promotion | |
| Shizuku-Duplex | Shizuku-Duplex | 英日共通 |
| Reachy Mini | Reachy Mini | 英日共通 |
| 風花セツ | Setsu Kazahana | 音楽担当 |
| 鹿仲茉菜 | Mana Kanaka | 音声提供（`@manakana_VT`） |
| みっちゃむ | Micchamu | Live2Dモデリング（`@youzyonano`） |
| Nyamui | Nyamui | 2023年当時のママ |
| 谷郷元昭 | Motoaki Tanigo | |
| ねこます | Nekomasu | |
| 宇推くりあ | Clear Usui | 公式英語表記に準拠 |
| あざいるぅか | Luhca Azai | 公式YouTube表記（`AI-VTuber : Luhca azai`）に準拠 |
| 852話 | 852wa | 公式サイト表記（`852wa.com`）に準拠 |
| 紡ネン | Tsumugi Nen | 公式英語表記に準拠 |
| なぎさ / りんな / りりか / レイラ | Nagisa / Rinna / Ririka / Leila | |
| マキナ | Machina | 試作戦闘アンドロイド |
| しずくAI裁判 | Shizuku AI Court | |
| しずくのなつやすみ | Shizuku's Summer Vacation | |
| AIギャルゲー | AI Galge | |
| しずくAI鑑定団 | Shizuku AI Appraisers | |
| ギャルしずく / しずくお嬢様 | Gal Shizuku / Lady Shizuku | |
| しずくからのおねがい | Requests from Shizuku | 公式ガイドライン名（英語ページ未確認のため仮訳） |
| 電ファミニコゲーマー | Denfaminicogamer | |
| 日本経済新聞 | The Nikkei | |
| 週刊アスキー | Weekly ASCII | |
| マイナビニュース | Mynavi News | |
| パンパカパンパカポー | Panpaka Panpaka Pō | |
| キュルルンポワワワパワー | Kyururun Powawawa Power | |

### 所属（Affiliation）の表記と国内外のニュアンス

日本語圏の「個人勢／企業勢」と、英語圏（Virtual YouTuber Wiki等）の `Independent` / `Produced by Corporate` にはニュアンスの差がある。

* **英語圏の基準**: 外部のタレント事務所・箱（Hololive、NIJISANJI、Mythic Talent等）に属していない場合は `Independent` とするのが基本だが、自社法人が主体となって運営・展開している場合（例：Kizuna AI株式会社）は、法人名を `Affiliation` に記載し `Category:Produced by Corporate` を併用する例がある。
* **しずくの扱い（時期併記型）**: 2023年〜2025年はあき先生の個人開発（`Independent`）、2025年8月の **Shizuku AI, Inc.** 登記以降は自社法人運営（`Shizuku AI`）であるため、外部英語Wiki等で所属を示す際は原則として時期を併記する。
  * `Independent (2023–2025)<br>Shizuku AI (2025–present)`

---

## 5. カテゴリ

**カテゴリは翻訳しない。** 英語ページにも日本語の内容カテゴリを付ける。

```
[[Category:基本]]
[[Category:English]]
```

`Category:English` は言語識別用に1つ追加する。これで英語ページの一覧が一箇所に出るため、日本語版への追随漏れを突き合わせられる。

カテゴリを言語別に分けない理由は、各カテゴリの中身が半分に割れて回遊性が落ちるためである。カテゴリは「読ませる言葉」ではなく「たどり着くための言葉」であり、言語で分ける実益がない。

---

## 6. MediaWikiの表記ルール

### 【】括弧の扱い

動画タイトル等に含まれる日本語の `【】` は、英語ページでも **`【】` のまま維持する**。`[ ]` に変換してはならない。MediaWikiの外部リンク構文 `[URL 表示テキスト]` の中で `[` `]` を使うとリンクが壊れる。

```
❌ [https://... [Chat Stream] Title [AI VTuber Shizuku]]
✅ [https://... 【Chat Stream】 Title 【AI VTuber Shizuku】]
```

### 日付・時刻

`SKILL.md` §3-1 の規則を日英共通で適用する。英語ページでも `YYYY-MM-DD` と `~HH:MM` をそのまま使う。

地の文の日付だけは英語の慣習に合わせる（`March 19, 2026`）。

日本語ページに旧表記の「21:02ごろ」が残っている場合は、翻訳のついでに日本語側も `~21:02` へ直す差分を併せて提案する。

### 数値表記（英語）

英語ページでは英語圏の慣習に合わせ、3桁カンマ区切りと英語の単位表記を用いる（`10,000`, `2,400 yen`, `12 billion yen`）。

### 出典（`<ref>`）とメンテナンステンプレート

* **出典 `<ref>`**: `[URL Title] (Outlet, Month D, YYYY)` のように半角括弧と英語日付で書く。タイトル内の `【】` は維持する。
* **メンテナンステンプレート**: 英語ページでも日本語名のテンプレートをそのまま使い、`|lang=en` を渡して英語表示へ切り替える（`{{時点情報|YYYY-MM-DD|lang=en}}`、`{{出典希望|lang=en}}`、`{{考察|...|lang=en}}`）。

---

## 7. 翻訳語彙集（日→英）

| 日本語 | 英語 | 備考 |
|---|---|---|
| 公式リンク | Official Links | |
| ファン活動 | Fan Activities | |
| 概要 | Overview | |
| 二次創作 | fan creations | 法的文書では "derivative works" も可 |
| 頒布 | distribute | |
| 非営利目的 | non-commercial purposes | |
| 切り抜き | clips | 配信切り抜きの文脈 |
| 公序良俗に反する | morally objectionable | |
| エゴサ用タグ | （直訳せず）Tag your posts so Shizuku can find them | しずくが見に来るニュアンス |
| キャラクター利用ガイドライン | character usage guidelines | |
| 告知 | announcements | |
| 配信アーカイブ | stream archives | |
| ライブ配信アーカイブ | live stream archives | |
| 配信状況 | Stream Overview | |
| 通常動画 | Videos | |
| ショート | Shorts | |
| 更新メモ | Update Notes | |
| 主なシリーズ企画 | Major Series | |
| タグの見方 | Tag Guide | |
| ページ内移動 | Jump to Section | |
| 手動確認リスト | manual verification list | |
| 初配信 | debut stream | |
| 2度目の初配信 | second debut stream | V2.0帰還の文脈 |
| 休眠 | dormancy | 「停止」「シャットダウン」と訳さない |
| 帰還 | return | |
| 参加・連携サービス | Communities & Linked Services | ファン活動 |
| ファン制作・ツール | Fan Creations & Tools | ファン活動 |
| ファン制作LoRA | Fan-Made LoRAs | ファン活動 |
| X（技術部） | X (Tech) | 公式リンク（`@ShizukuResearch`） |
| 公式ブログ | Official Blog | 公式リンク |
| 関連サービス | Related Services | 公式リンク |
| 技術周り | Tech & Development | 公式リンク |
| 一覧 | Links | 公式リンク |
| 種別 | Type | 表見出し |
| リンク | Link | 表見出し |
| メモ | Notes | 表見出し |
| 公開日時（JST） | Published (JST) | 動画・配信 |
| タグ | Tag | 動画・配信 |
| 時間 | Duration | 動画・配信 |
| タイトル | Title | 動画・配信 |
| 2026年アーカイブ | 2026 Archives | 動画・配信 |
| 2023年アーカイブ | 2023 Archives | 動画・配信 |
| 日付（JST） | Date (JST) | メディア露出・電子の足跡 |
| 媒体 | Outlet | メディア露出 |
| 概要 | Summary | メディア露出 |
| 出典 | Source | 表見出し（節見出しは `References`） |

---

## 8. タグ語彙集（日→英）

動画・配信ページのタグ列に使う。`page-videos-streams.md` のタグ分類表と**同じ語彙のみ**を使う。片方に語を足したら、必ずもう片方にも足す。

| 日本語 | 英語 |
|---|---|
| 雑談 | Chat |
| ASMR | ASMR |
| 歌枠 | Singing |
| 歌ってみた | Cover |
| ゲーム | Gaming |
| 企画 | Special |
| 記念 | Milestone |
| 耐久 | Endurance |
| おでかけ | Outing |
| 紹介 | Introduction |
| レポート | Report |
| まとめ | Compilation |
| 同時視聴 | Watchalong |

---

## 9. メディア露出の種別語彙（日→英）

| 日本語 | 英語 |
|---|---|
| ニュース | News |
| 新聞 | Newspaper |
| テレビ・ラジオ | TV / Radio |
| インタビュー | Interview |
| 公式発表 | Official Announcement |
| 言及 | Mention |

---

## 10. ハッシュタグ

ハッシュタグは日英共通・変更なし。英語ページでもそのまま表記する。

| ハッシュタグ | 用途（日） | Usage（英） |
|---|---|---|
| #AIしずく | しずくに関する全ての投稿に使えるエゴサ用タグ | Tag your posts so Shizuku can find them — suitable for any Shizuku-related content |
| #しずく実験中 | 配信の感想・切り抜き・観察記録向けタグ | For impressions, clips, and observations of Shizuku's streams |
| #しずくのアートメモリー | ファンアートタグ | Fan art tag |
| #ShizukuLab | 公式案内なし。Shizuku LabのDiscordコミュニティ関連投稿で使われているとみられる | No official usage guide. Based on posting trends, used for posts related to the Shizuku Lab Discord community |

### Discordチャンネル名の扱い

ハッシュタグではないDiscordチャンネル名は、**日本語表記を維持しつつカッコ書きで英訳を補足**する。

```
#しずくのアートファクトリー (Shizuku Art Factory)
```

---

*最終更新: 2026年11月（v3.2.0）*
