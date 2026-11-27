# X（Twitter）ログ データ仕様書

本仕様書は、`logs/twitter(x)/` に保存するXログのデータ形式・匿名化規則・品質ラベル・収集フローを定義します。`docs/archive-policy.md` および `tools/shizuku-pipeline/DATA-ISSUES.md` を補完する位置づけです。

---

## 1. ファイル配置と基本フォーマット

- **保存先**: `logs/twitter(x)/<ハンドル>/`。`@` を除いた投稿者ハンドルをフォルダ名に使い、全行の `author` をそのハンドルにそろえる。
- **ファイル分割**: アカウントごとに JST の年・月で分ける（例：`Shizuku_AItuber/202601-05.txt`、`cumulo_autumn/2026.txt`、`ShizukuResearch/2026.txt`）。`post_id` は全ファイルを通して一意とする。
- **取り込み**: S0 はアカウントのフォルダ構成を保って `tools/shizuku-pipeline/data/raw/x/` に同期する。S1 は `author` を保持した月別JSONLを生成する。 [収集・統合手順](../tools/workflows/x_collection_workflow.md)
- **文字コード・改行**: UTF-8（BOMなし）、改行コード **LF（`\n`）** に統一
- **区切り文字**: タブ区切り（TSV）。セル内の改行・タブはエスケープまたはスペース正規化し、1レコード1行を厳守する
- **並び順**: `date_utc` の降順（または昇順）に統一し、後から追記した行だけを末尾に不規則配置しない
- **空期間ファイル**: 休眠期等で投稿が0件の年は「`なし`」と記録してよい（`DATA-ISSUES.md §6` 準拠）

---

## 2. 列定義（新スキーマ）

肥大化を抑えつつ追跡性と品質監査を可能にするため、連番 `id` 列および冗長な `https://x.com/<handle>/status/...` 文字列列を廃止し、`post_id` を主キーとします。

| 列名 | 型 / 形式 | 必須 | 説明・ルール |
|---|---|:---:|---|
| `post_id` | 文字列（数値ID） | ○ | XのステータスID。URLはパイプライン・Wiki出力時に `https://x.com/i/status/{post_id}` として生成する（ハンドル名を含めず、改名耐性・匿名性を確保） |
| `date_utc` | ISO8601 (`YYYY-MM-DDTHH:MM:SS.000Z`) | ○ | 投稿日時（UTC）。年表・Wiki反映時はパイプライン側でJST（+9時間）へ変換する |
| `author` | 文字列 | ○ | 投稿者のハンドル（例：`Shizuku_AItuber`, `cumulo_autumn`） |
| `type` | 列挙値 | ○ | `CONTEXT_TWEET`（通常投稿） / `REPLY`（返信。引用を兼ねる場合は引用列も保持） / `QUOTE_RETWEET`（引用RT） / `RETWEET`（単純RT。※原則除外対象、§5参照） |
| `text` | 文字列 | | 投稿本文。FxTwitter等で復元した標準絵文字・展開済みURLを保持する。演出上の意図的な文字化け（例：2023-05-24 `1661325152653815808`）は原文のまま残す |
| `extracted_urls` | 空白区切りURL | | 本文・`facets` から抽出した外部URL。`t.co` は展開後の正規URLを格納する |
| `quote_post_id` | 文字列（数値ID） | | 引用元（`QUOTE_RETWEET`）のステータスID。従来の `引用URL` 列を統合・ID化 |
| `quote_author` | 文字列 | | 引用元の投稿者。ホワイトリスト対象は実ハンドル、一般視聴者は `User_XXXXXXXX`（§3参照） |
| `quote_text` | 文字列 | | 引用元の本文。一般視聴者の引用本文は保存しない（§3参照） |
| `reply_to_post_id` | 文字列（数値ID） | | 返信先（`REPLY`）の親ステータスID。確認用導線（`https://x.com/i/status/{reply_to_post_id}`）として保持する（§3参照） |
| `reply_to_author` | 文字列 | | 返信先の投稿者。ホワイトリスト対象は実ハンドル、一般視聴者は `User_XXXXXXXX` |
| `media_urls` | 空白区切りURL | | 添付画像・動画サムネURL。`pbs.twimg.com` の画像URLは原則 `name=orig`（または `large`）へ正規化する |
| `likes` | 整数 / 空欄 | | いいね数。空欄は「未取得」または「0件の可能性がある未確定値」（`quality_flags` に `count_uncertain` を付与） |
| `reposts` | 整数 / 空欄 | | リポスト数（同上） |
| `replies` | 整数 / 空欄 | | 返信数（同上） |
| `views` | 整数 / 空欄 | | インプレッション数 |
| `snapshot_date` | `YYYY-MM-DD` | ○ | 本文・関係性データの取得日（JST） |
| `metrics_date` | `YYYY-MM-DD` | | 反応数（`likes`〜`views`）の取得日。本文を後日FxTwitterで補完し、反応数だけ旧時点の値を残す場合に `snapshot_date` と区別するために用いる |
| `source_method` | 列挙値 | ○ | 取得経路ラベル（§4参照） |
| `quality_flags` | `\|` 区切りフラグ | | 欠落・注意点フラグ。問題がない行は空欄（0バイト）とし、肥大化を防ぐ（§4参照） |

---

## 3. 匿名化と追跡性のバランス（`REPLY` / `QUOTE_RETWEET`）

しずくは「誰とどのようなやり取りをしたか」の関係性が重要であるため、相手アカウントを一律削除するのではなく、YouTubeチャット匿名化（`tools/scripts/anon_whitelist.txt` / `anon_whitelist_x.txt`）と同じ二層方式を採用します。

1. **ホワイトリスト対象（公式・開発者・コラボ相手・公的アカウント）**
   - `@Shizuku_AItuber`、`@cumulo_autumn`（あき先生）、`@Nya6y`（ママ）、コラボ共演したVTuber/AI VTuber、公式メディア等。
   - `reply_to_author` / `quote_author` に実ハンドルを保持し、`reply_to_post_id` / `quote_post_id` もそのまま公開TSVに記録して完全な追跡性を維持する。
2. **一般視聴者（非ホワイトリスト）**
   - `reply_to_author` / `quote_author` は **`User_XXXXXXXX`**（共通ソルトによるハッシュID）へ変換し、「同一ユーザーとの継続的な掛け合い」を識別可能にしつつ個人アカウント名を伏せる。
   - **一般視聴者の発言本文はTSVに保存しない**（相手の文章の無断転載・原文検索による個人特定を防ぐため。Wiki記載時は「【ご主人様のコメント】」として要約・匿名化する）。
   - **確認用導線として `reply_to_post_id` のみ保持する**: しずく本人の投稿と「リプがあった導線」を残し、後から文脈を詳しく確認する必要が生じた場合に `https://x.com/i/status/{reply_to_post_id}` へ直接アクセスして目視確認できるようにする（※相手アカウントが削除・非公開化した場合は辿れなくなる点、およびID単体には `@handle` を含まないもののX上では公開ポストへ遷移できる点は仕様上の前提として扱う）。

---

## 4. `source_method` と `quality_flags` の定義

データサイズを増やさずに出所と欠落リスクを管理するため、以下の短いコードを使用します。

### `source_method`（取得経路）
- `web_dom`: ブラウザ手動スクロール＋コンソールスクリプトによるDOM抽出（旧形式の主要経路）
- `fx_status`: FxTwitter API（`status` エンドポイント）による取得
- `fx_thread`: FxTwitter API（`thread` / `conversation` エンドポイント）による補完
- `web_dom+fx`: `web_dom` で取得した行を、保存済みまたは再取得した FxTwitter 応答で本文・引用・URL補完したもの
- `fxtwitter`: 既存TSVに残る旧ラベル。status・thread等の区別が確認できないため履歴として保持する。
- `web_dom+fx+fx_thread`: このうち web_dom+fx に加え、`thread` または `conversation` で返信先を補完したもの

### `quality_flags`（ASCIIの `|` 区切り・正常時は空欄）
- `no_emoji`: DOM抽出時に標準絵文字（`img[alt]`）が欠落している可能性
- `trunc_text`: 本文が文字数制限等で途中切れ（末尾 `…` 等）
- `trunc_quote`: 引用本文が120文字等で途中切れ
- `short_url`: 本文・抽出URLに `t.co` 未展開または `…` 省略が残存
- `missing_parent`: `type=REPLY` だが `reply_to_post_id` が未取得
- `count_uncertain`: `likes` / `reposts` / `replies` の空欄が「0件」か「未取得」か判別不能
- `dom_swapped_fixed`: 旧 `web_dom` で引用元本文が本人本文に誤混入していたものを FxTwitter により修復済み
- `error_fixed`: 旧ログの `#ERROR!` 等を FxTwitter により修復済み

---

## 5. 収集ルールと単純リポスト（`RETWEET`）の扱い

- **2段階収集の原則**: FxTwitter の `statuses` や `search` は過去ログ・返信の網羅取得に適さないため（2026年11月検証で返信取得率0.1%、検索は503）、「**Web手動スクロール／定期スクリプト等で `post_id` を発見する**」段階と「**`post_id` を FxTwitter `status`（親欠損時は `thread`）に渡して確定データを取得する**」段階を分離する。
- **単純リポスト（`RETWEET`）の扱い**: 検索画面やタイムライン取得では、本人が他人の投稿を単純RTしたものも混入する。FxTwitter で該当IDを取得すると元投稿者の発言として返るため、**原則として収集対象から除外**する。記録する必要がある場合も `type=RETWEET` を明示し、パイプライン（`s1_normalize.py`）側でしずく本人の発言・名言抽出から自動除外する。
- **周辺アカウントの収集方針**:
  - `@Shizuku_AItuber`（本体）に加え、仕様変更・障害・運営経緯の一次根拠として **`@cumulo_autumn`（あき先生）** を継続収集対象とする。
  - **`@Nya6y`（ママ）** はアカウント消失済みのため、Wayback Machine・togetter・引用RT断片など、ネット上に残存する確認可能な断片のみを出典付きで別枠管理する。
