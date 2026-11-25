# AI-VTuber-Shizuku-log

AI VTuber「[しずく](https://shizuku.ai/)」の配信・動画・SNSの発言を保存する、有志による非公式アーカイブです。元の発言を探し、ログ分析、Fandom Wikiの編集、ペルソナ研究に再利用するための資料とツールをまとめています。

[YouTube](https://www.youtube.com/@AIVtuber_Shizuku) / [X](https://x.com/Shizuku_AItuber) / [公式サイト](https://shizuku.ai/) / [Shizuku Fandom](https://shizuku.fandom.com/)

このREADMEは、資料の保存先と作業の入口を案内します。AIエージェントの実行規約は [AGENTS.md](AGENTS.md)、詳しい操作は各ツールの手順書を参照してください。

## GitHubとFandom Wikiの役割

GitHubには、収録したログと、その出所や検証過程を後から確かめるための記録を残します。Fandom Wikiでは、人が確認した事実を読者向けに整理し、元動画の該当時刻など、根拠へたどれる出典を添えます。

収録済みの範囲、保存できていない資料、取得・加工の記録方法は [ログの保存と検証の方針](docs/archive-policy.md) にまとめています。

## 保存先と文書の役割

```text
logs/
  youtube/<年>/<日付_タイトル>/   動画情報・字幕・チャット・コメント
  twitter(x)/<ハンドル>/        Xの収集ログ（年・月別TSV）
persona/                        人格・特性・エピソード等の分析資料
tools/                         下記の収集・分析・編集ツール
outputs/                        中間データ・調査案・実行結果（Git管理外）
AGENTS.md                       エージェント向けの実行規約
Readme.md                       利用者向けの入口（本書）
```

`tools/` の主な入口は次のとおりです。

| 保存先 | 役割 |
|---|---|
| `tools/scripts/` | ログ収集、匿名化、字幕変換、文字起こし等の単体スクリプト |
| `tools/prompts/` | ログ整形・分析・抽出用のプロンプト |
| `tools/workflows/` | 手動またはLLM併用の詳しい手順 |
| [`tools/skills/`](tools/skills/README.md) | Wiki編集、動画の再生時間収集、YouTubeコメント用の目次作成 |
| `tools/shizuku-pipeline/` | ログからWiki候補を作る独立した半自動パイプライン |

### ログを読むとき

- `<動画ID>.info.txt`：収録した動画のタイトル、日付、説明欄など。
- `<動画ID>.ja.srt` / `*.ja.sbv.txt`：YouTubeから取得した字幕。自動字幕の誤認識に注意してください。
- `<動画ID>.transcribe.txt`：字幕がない配信からローカルASRで生成した、未確認の文字起こし。
- `<動画ID>.nemotron-3.5-transcribe.txt` / `<動画ID>.qwen3-asr-1.7b.txt`：既存字幕と比較するために、動画の音声から別途生成した未確認の文字起こし。
- `<動画ID>.screen-ocr.txt`：動画内の発言欄を画面から読み取った、時刻付きの未確認テキスト。
- `<動画ID>.live_chat.txt` / `*.comments.txt`：ライブチャット・通常コメント。一般視聴者名は匿名化しています。
- `*.compiled.md`：AIで整形・要約した派生資料。事実の確認では元の字幕・チャット・動画へ戻ります。

本人の発言、視聴者のコメント、分析者の解釈を区別し、引用や出来事には動画ID・日付・タイムスタンプを残します。字幕やASRを逐語引用として確定するには、元動画の確認が必要です。

## よく使う作業

コマンドはリポジトリのルートから実行します。依存関係はツール単位で、リポジトリ全体の共通環境定義はありません。

| 作業 | 入口 |
|---|---|
| 終了済みの未収録配信を追加する | 下記「ログの更新」 |
| 未収録の X 投稿をアカウント別に追加する | [Xログの収集・統合手順](tools/workflows/x_collection_workflow.md) |
| 字幕の補完・日本語ASRの再生成 | [字幕なし配信の文字起こし](tools/workflows/字幕なし配信の文字起こし.md) |
| 既存字幕と比較するNemotron文字起こし | [比較用の一括処理](tools/workflows/字幕なし配信の文字起こし.md#既存字幕と比較するnemotron文字起こし) |
| 配信ログを整理・分析する | [分析ワークフロー](tools/prompts/shizuku_analysis/analysis_workflow_guide.md) |
| 動画内の発言欄・焼き付きチャットをOCRする | [Visual Chat-Timeline Sync](tools/workflows/Visual%20Chat-Timeline%20Syncの手順書.md) |
| LLMで統合ログ・タイムスタンプを作る | [ログ整形の手順書](tools/workflows/youtube_log_prompt_v-divの手順書.md) |
| YouTubeコメント用の目次を作る | [タイムスタンプ作成スキル](tools/skills/youtube_timestamp_comment_skill/README.md)。既存目次の充実度を確認→不足時にコメント再取得→必要な案を生成→ユーザーが手動投稿→公開コメントを再収録。YouTubeとWikiの一覧照合は別作業 |
| Wiki記事を調査・提案・公開する | 下記「Fandom Wikiの編集」 |
| 半自動パイプラインでWiki候補を作る | [パイプラインのマニュアル](tools/shizuku-pipeline/MANUAL.md) |
| ペルソナを更新する | [分析プロンプト](persona/99_prompts/analysis_prompt.md) |

### ログの更新

```powershell
# 未収録の終了済み配信を確認する（取得しない）
python tools/scripts/update_shizuku_logs.py

# 未収録分を匿名化して取得・保存する
python tools/scripts/update_shizuku_logs.py --apply
```

予約枠と配信中の動画は対象外です。保存先は `logs/youtube/<年>/<日付_タイトル>/` で、既存の動画IDは重複取得しません。

新規配信に字幕がなければ、日本語ASRを実行します。既定はspeech.cppのQwen3-ASRを日本語指定で使い、1時間を超える音声は55分ごとに分割して、時刻を補正した文字起こしを結合します。yt-dlpに加え、ffmpegとspeech.cppが必要です。

```powershell
# 収録済み動画の字幕を補完する
python tools/scripts/transcribe_youtube.py <動画ID> --profile japanese

# 明示的に日本語ASRを作り直し、確認用の中間データを残す
python tools/scripts/transcribe_youtube.py <動画ID> --profile japanese --replace-transcript --keep-staging
```

文字起こしの中間データは `outputs/shizuku-transcribe/`、ログ更新の一時出力は `outputs/shizuku-log-update/` です。成功・保存確認後の後片付けと、失敗時の再開方法は [手順書](tools/workflows/字幕なし配信の文字起こし.md) と [AGENTS.md](AGENTS.md) を参照してください。

匿名化スクリプトは対象ファイルを必ず明示します。字幕変換・伏せ字化等は、実行前にスクリプトの説明や入力先を確認してください。特に `censor_sbv.py` は入出力先が固定された作業用スクリプトです。

## Fandom Wikiの編集

[しずくWiki編集スキル](tools/skills/shizuku-wiki/SKILL.md)を使い、元ログから情報をページ別に振り分け、前後の文脈に合う差分を作ります。連続企画の専用記事、新規ページも対象です。

1. 現在のWikiソースを確認する。新規ページでは正式名称と未作成を確認する。
2. 字幕・公式チャット・説明欄・公式発表等を調べ、追記・置換または新規記事の本文案を作る。
3. 公開する対象と内容を確認できる案に対して、ユーザーの承認を受ける。
4. 反映直前に競合を検査し、公開後は保存本文・出典・リンク・カテゴリを確認する。

終了したリアルタイム企画は、当時の参加方法と現在のアーカイブ視聴を区別します。しずくの記憶についての語りと、サービスのデータ保存仕様も分けて扱います。

- [スキルのREADME](tools/skills/shizuku-wiki/README.md)：導入、BotPasswordの登録・権限、既存更新と新規作成の違い。
- [プロンプトパターン集](tools/skills/shizuku-wiki/PROMPT_PATTERNS.md)では、Wikiソースの渡し方と、更新案・点検・翻訳などの依頼文を確認できます。
- [記事ワークフロー](tools/skills/shizuku-wiki/references/article-workflow.md)：調査、文脈確認、差分、API反映、公開後の確認。
- [文体ガイド](tools/skills/shizuku-wiki/references/tone-style-guide.md)：しずくを主語にした文章、呼称、引用の扱い。

`update_videos_streams.py` は「動画・配信」専用です。他ページや新規記事の公開へ転用しません。Wikiの調査案・承認記録・公開結果は `outputs/shizuku-wiki/` に保存し、一次ログや配布スキルへ混ぜません。

認証にはWindowsユーザー環境変数 `SHIZUKU_FANDOM_BOT_USERNAME` と `SHIZUKU_FANDOM_BOT_PASSWORD` を使います。編集する正式なページ名の許可と、新規作成時の追加権限が必要です。設定・非表示の確認・再読み込みは [スキルのREADME](tools/skills/shizuku-wiki/README.md) を正本とし、値はチャットやファイルへ書きません。

## 取り扱いと貢献

- 本リポジトリは有志による非公式プロジェクトです。Wikiへの編集作業も有志の取り組みです。
- 収録資料の権利は、Shizuku AIおよび各権利者に帰属します。
- 一般視聴者名は `User_XXXXXXXX` 形式の匿名IDを維持します。一部の公式アカウント等は既存のホワイトリストに従います。
- Cookie・APIキー・トークン・匿名化前の対応表・ローカル固有の絶対パスを、公開用成果物へ含めません。
- 一次ログは証拠資料として扱います。訂正する場合は原文との差と根拠を残し、まとめて整形しません。
- AI生成の要約や分析は原発言と異なる可能性があります。モデル別の経験則を、すべての環境での保証として扱いません。

資料や手順の改善はPull Requestで提案できます。ログの訂正には参照元と時刻を添えてください。エージェントは [AGENTS.md](AGENTS.md) の検証・完了報告の規約も確認してください。
