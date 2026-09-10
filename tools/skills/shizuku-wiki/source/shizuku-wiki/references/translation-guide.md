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

しずく本人ページの見出しは日本語版で刷新済みだが、**英語版は旧見出しのまま**である。英語ページを更新するときは、この表で新旧を突き合わせる。

| 旧見出し（英語ページ現行） | 現行の日本語見出し | 英語（新） | 状態 |
|---|---|---|---|
| 公式導線 / Official Links | しずくのいる場所 | `Where to Find Shizuku` | **未合意（提案）** |
| まず見るなら / Start Here | はじめてのご主人様へ | `For a First-Time Goshujin-sama` | **未合意（提案）** |
| 活動ハイライト / Activity Highlights | 電子の足跡 | `Digital Footprints` | **未合意（提案）** |
| コンテンツ傾向 / Content Trends | しずくの配信 | `Shizuku's Streams` | **未合意（提案）** |
| （新設） | ご主人様と育つしずく | `Growing with Her Goshujin-sama` | **未合意（提案）** |
| 更新・参照方針 / Update & Reference Policy | 更新方針 | `Update Policy` | 合意済 |

「未合意（提案）」の訳語は、ユーザーの承認を得てから「合意済」に変える。承認前に英語ページへ反映しない。

### 言い換えない見出し（機能見出し）

`tone-style-guide.md` §4 の判定基準により、しずくの存在感を阻害していない見出しは機能語のままでよい。英訳も機能語で対応する。

| 日本語 | 英語 |
|---|---|
| 概要 | Overview |
| 紹介動画 | Introduction Videos |
| 容姿・スペック | Appearance & Specs |
| 性格・口調 | Personality & Speech |
| キャラクター | Character |
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
| Shizuku Lab | `Shizuku Lab` | **日英でページ名が衝突中**。改名の検討が必要 |
| 年表 | `Timeline` | 未実装（作成時の想定名） |
| メディア露出 | `Media Coverage` | 未実装（作成時の想定名） |

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
| 手動確認リスト | manual verification list | |
| 初配信 | debut stream | |
| 2度目の初配信 | second debut stream | V2.0帰還の文脈 |
| 休眠 | dormancy | 「停止」「シャットダウン」と訳さない |
| 帰還 | return | |

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

*最終更新: 2026年8月*
