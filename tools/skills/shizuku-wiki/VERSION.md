# v3.3.0

- **GitHub（研究基盤）と Fandom Wiki（公開の入口）の二層構造**を `references/external-wikis-sync.md` に定義し、生ログ・取得メタデータ（取得日時・公式字幕/ASR・AI加工版）・未収録範囲リスト・`ai_hypothesis` と、Wiki側の `observed` 事実・タイムスタンプ逆引き導線の役割分担を明記。
- `SKILL.md` §3-2 および `references/editorial/QUALITY-GATES.md` に、**「本人発言の記録」と「技術資料・確定仕様の根拠」の切り分け**を追加（`<ref>` 形式を増やさずチェック工程で制御）。
- `references/article-workflow.md` に、中間データ・調査メモへの取得メタデータ保持、未匿名化の個人生ログの非収録境界、および **`ai_hypothesis` を確定本文案に混ぜず別枠提示する分離ゲート**を追加。
- `references/tone-style-guide.md` §5・`references/page-timeline.md` §7 に、AI言動の**「時系列併記」原則**（裏付けのない伏線回収・意図的因果の禁止）を追記。
- `references/editorial/style-exceptions.md`・`references/editorial/QUALITY-GATES.md` に、**「綺麗に直しすぎない」原則のページ別適用**（`しずく` 本人ページ全般は原文・ノイズ保持と標準語補足の並記、`年表`・`メディア露出` 等は情報索引として均質化）を明記。
- `references/page-shizuku.md`・`references/page-fan-activities.md` に、「面白さ」と「歴史的重要性」の切り分けおよび匿名化前提の収録範囲を補足。
- `references/external-wikis-sync.md`・`references/monitoring-runbook.md` に、**出典ロンダリングの防止**・**健全な相互検証**・年次見直しでのルール間矛盾照合を追加。

# v3.2.4

- `references/external-wikis-sync.md` の Virtual YouTuber Wiki（Fandom）ルールに、コミュニティ側の編集基準（`affiliation` の年号なし表記、`character_designer` の対象範囲、`History` / `Events` / `Trivia > Miscellaneous` / `Trivia > Shizuku AI, Inc.` の分離基準、`* ` 箇条書き・過剰太字の抑制・`[[w:c:shizuku:...]]` インターウィキ記法）を追記。

# v3.2.3

- `しずく` 本人ページに新見出し `== しずくの観察メモ ==`（15節体制、`== 電子の足跡 ==` と `== クレジット ==` の間）を追加し、`<references />`（`出典`）より前に配置することで出典エラーを防ぐ構成を `references/tone-style-guide.md`・`references/page-shizuku.md` に反映。
- 最末尾の `== おまけ ==` はあき先生の三面図を置く固定枠として維持する方針を明記。
- `references/translation-guide.md` §2 に `しずくの観察メモ`（`Shizuku Observation Notes`・未合意提案）を追記。

# v3.2.2

- `references/external-wikis-sync.md` のピクシブ百科事典ルールに、更新確定後の最終出力時に「編集した内容を5字以上250字以内」の硬めな更新報告文をあわせて出力する仕様を追記。

# v3.2.1

- `references/external-wikis-sync.md` のピクシブ百科事典方針を具体化し、Shizuku Wiki側の硬い文体・過剰な日付で元の「ゆるい読み物」の勢いを上書きしないルール、および日本語圏向け媒体への英語圏向け情報の非混入ルールを明記。

# v3.2.0

- `references/external-wikis-sync.md` を新設し、5媒体（Wikipedia日本語版・ピクシブ百科事典・Virtual YouTuber Wiki・Shizuku Wiki・Grokipedia）の役割分担・ライセンス注意（CC BY-SA 4.0/3.0非互換）・コンフリクト事前確認・双方向更新ワークフローを定義。
- `references/translation-guide.md` §4 に、国内外の「個人勢／企業勢」と英語圏の `Independent` / `Produced by Corporate` のニュアンス差、およびしずくの時期併記基準（`Independent (2023–2025)` / `Shizuku AI (2025–present)`）を追記。
- `SKILL.md` §7 の参照表に `references/external-wikis-sync.md` を追加。

# v3.1.13

- `SKILL.md` §0-3 に、複数ページや長大ページの一括全文出力時は、URL・記法検証済みの `.wikitext` ファイル一式を `.zip` で提示できる例外を追記。
- `SKILL.md` §8 および `references/translation-guide.md` §3 を更新し、`Shizuku Lab` の英語版ページ名を `Shizuku Lab (EN)`（`{{DISPLAYTITLE:Shizuku Lab}}`・内部リンクは `[[Shizuku Lab (EN)|Shizuku Lab]]`）として確定。
- `SKILL.md` §8 および `references/translation-guide.md` §3 に、`編集者の方へ` は人的リソースおよび英語側単独編集による上書き防止のため当面日本語のみで維持し、英語ページからは `[[編集者の方へ]]` で参照する方針を明記。

# v3.1.12

- `references/translation-guide.md` §2 の `[[Shizuku]]` 未合意見出し5件を「合意済」へ更新し、`ご主人様と育つしずく` を `Shizuku & Goshujin-sama: Growing Together` とした意図（見出しで性別的表現を前景化せず、しずくとご主人様を対等に並べる方針）を明記。
- `references/translation-guide.md` §4・§6・§7 に、新出の固有名詞（`Luhca Azai`、`Clear Usui`、`Tsumugi Nen`、`852wa`、`Mana Kanaka`、`Shizuku ID`、`Shizuku-Duplex` 等）、英語数値表記、英語 `<ref>` 書式、新見出し・表ヘッダ語彙（`X (Tech)` 等）を追記。
- `SKILL.md` §3-5・§8、`references/translation-guide.md` §3、`references/monitoring-runbook.md` §4 を更新し、`Timeline`・`Media Coverage` の実在状況を同期するとともに、メンテナンステンプレート3種（`{{出典希望}}`・`{{時点情報}}`・`{{考察}}`）の `lang=en` 分岐仕様を追加。

# v3.1.11

- `references/page-videos-streams.md` に、ショート動画（`/shorts`）の例外掲載基準（独自企画や1000万〜1億再生規模の注目作）、`== 配信状況 ==` 本数行への `{{時点情報|YYYY-MM-DD}}` 1箇所付与ルール、および案内ブロック（タグの見方・ページ内移動・主なシリーズ企画）・2023-01-19初期テスト配信の保護方針を追記。
- `references/editorial/page-profiles.md` の `動画・配信` 行を更新し、表外案内文の局所推敲と表内データ非改変を明記。
- `references/translation-guide.md` §7 に `主なシリーズ企画`（Major Series）、`タグの見方`（Tag Guide）、`ページ内移動`（Jump to Section）を追記。

## v3.1.10

- `references/page-media-coverage.md` §0 に、`動画・配信` 以外のページでも Fandom MediaWiki API による最新ソース・関連ページの一括取得を活用できる旨を追記。
- `references/page-media-coverage.md` §1 に、批判的・否定的な報道であっても一次報道であれば索引から除外せず、媒体を主語にした帰属表現と `== 注記 ==` での公式見解併記で扱う方針を追記。
- `references/page-media-coverage.md` §2 に、記事原題に含まれる本名は `<ref>` 内で維持しつつ、概要欄の地の文では活動名・肩書き（例：`Shizuku AIのCEO`）を用いる切り分けを明記。
- `references/page-media-coverage.md` §3 に、公開日不明のイベント・協賛ページの日付列ルール（開催期間のJST換算＋注記明記）と、`公式発表` と `ニュース`・`新聞` を分けて同種別同士で統合する基準を追記。

## v3.1.9

- `references/page-fan-activities.md` の「二次創作・キャラクター利用」を早見表＋公式Webガイドライン（`https://shizuku.ai/ja/character-guideline/`）および `[[編集者の方へ]]` への一本化方針に整理（Discordチャンネルへの案内を削除し、OK/NGの重複箇条書きを廃止）。
- `references/page-fan-activities.md` の「ハッシュタグ」を汎用性・利用頻度の高い3種に絞り、その他は `[[ハッシュタグ]]` へ集約する方針を明記。

## v3.1.8

- `SKILL.md` §3-4 に MediaWiki の箇条書き（`* ` 必須、`- ` 禁止）と改行・段落（`\n` / `\n\n` / `<br>` / `<br><br>`）のルールを追記。
- `scripts/editorial_pipeline.py` に `wikitext_lint` を追加し、`audit` 実行時に `- ` 箇条書きや意図しない単一改行を自動検出するよう拡張（単体テスト追加）。
- `references/page-fan-activities.md` のページ構成を「参加・連携サービス」「ファン制作・ツール」「二次創作・キャラクター利用（早見表付き）」および `[[ハッシュタグ]]` との役割分担に合わせて更新。

## v3.1.7

- `SKILL.md` §3-2 に、公開URLが存在しないサーバー内情報（Discord内機能・チャンネル構成など）は `{{時点情報|YYYY-MM-DD}}` と `{{出典希望}}` を併記する方針を追記。
- `references/editorial/page-profiles.md` の「ファン活動」行を「ファン活動 / Shizuku Lab」へ拡張。

## v3.1.6

- `references/page-official-links.md` §1 の分類を修正し、技術発信が中心の公式ブログを「関連サービス」から「技術周り」へ移動。

## v3.1.5

- `references/page-official-links.md` §1・§2 に、会社側の採用ページ（`/careers/`）や現状更新・連動のない開発プラットフォーム（Hugging Face / GitHub）を載せない方針（重要更新時に再判断）と、しずく優先の掲載順を明記。

## v3.1.4

- 公開日・更新日の記載がない常設Webページを出典（`<ref>`）にする場合の日付省略ルールを `SKILL.md` §3-2 に追記。
- `references/page-official-links.md` §1 の掲載基準を、しずく優先・関連サービス・技術周り・公式コミュニティを含む基準に整理し、迷う候補は別途提案する方針を明記。
- 公式ガイドラインの参照先を `[[編集者の方へ]]` に統一（`SKILL.md` §3-8、`references/page-fan-activities.md` §3）。

## v3.1.3

- 相談・確認先を「トークページ」から「Discord（推奨）またはShizuku AIのメール窓口（`contact@shizukuai.com`）」へ統一（`tone-style-guide.md` / `page-fan-activities.md`）。
- 公式の「AI VTuber「しずく」キャラクター利用ガイドライン」のURL（`https://shizuku.ai/ja/character-guideline/`）、正式名称、問い合わせ先（`contact@shizukuai.com`）を `SKILL.md` §3-8 と `page-fan-activities.md` §3 に記録。
- `SKILL.md` §0-4 に「編集者の方へ」の必須ルールと本スキル（推奨・任意支援）の位置づけを補足。
- `references/editorial/page-profiles.md` に運用ガイドページ（`編集者の方へ` 等）のプロファイルを追加。

## v3.1.2

- Webチャット等での大規模改修時に、機械検証を条件として ` ```wikitext ` コードブロックでの全文出力を例外許容（AIエージェント／bot更新向けの差分既定は維持）。
- 年表の通常回・2回目以降について、後日の大きな節目と連続する過去トピックを掘り下げる場合の例外追記ルールを明記。
- 年表の中見出し（`=== フェーズ名（期間） ===`）と冒頭リード文（役割分担＋しずくの実発言引用）の指針を追加。
- VisualEditor 由来の `:0`・`:1` 等の機械的な `ref name` を一括メンテナンス時に整理できる例外、および YouTube 出典の媒体名重複禁止を追記。

## v3.1.1

- 短い見立てをインライン型の考察テンプレートで示す。本文・表の外部リンクと掲載済みの公式画像の確認方法を追記し、身長例にご主人様との関係と可変の目的を戻した。

## v3.1.0

- 本人ページを14節に整理。外見・性格は散文、特殊機能・衣装は1項目1行とし、旧「キャラクター」節の内容の移行先を日英のガイドに記載。
- 呼称の初回注釈、誕生前の主語、本人のAIらしい持ちネタ、用途別の器の書き方を明文化。
- 事実と考察の段落を分け、出典URL、引用原文、衣装などの視覚資料を確認する手順を追加。

## v3.0.0

- 年表は初稿前に出来事の種類・確認段階・しずくとの関係を整理し、しずくの生涯を中心に書く。技術的な発表を中心に残す場合は、検討した別案と正確さのために必要な理由を記録する。
- 視点・事実の範囲・粒度・文脈を全追加・置換項目で審査する。記録の欠落・保留・審査後の本文変更を検出し、公開提案とAPI反映の前に確認する。
- yomiyasuの旧版由来の抜粋を、添付のv3.1.0本体とWiki用アダプターに更新した。
- 編集用の正本をv2.0.0の配布物と同期したうえで更新し、`shizuku-wiki-v3.skill` として保存。v1・v2の配布物を保存したまま利用できる。
