# AGENTS.md — shizuku-pipeline

このファイルは `tools/shizuku-pipeline/` 以下に適用され、ルートの `AGENTS.md` を補足します。このパイプラインは、ログからWiki更新候補を生成する半自動システムです。最終判断と公開は人間が行います。

## 必読順

1. 本書 — エージェント向けの共通指示、引き継ぎ、運用上の注意
2. `docs/ARCHITECTURE.md` — 設計思想と境界
3. `docs/SPEC.md` — スキーマ、ID、状態遷移、CLIの契約
4. 作業内容に応じて `MANUAL.md`、`DATA-ISSUES.md`、`docs/PLAN.md`、`docs/ROADMAP.md`

実装と文書が食い違う場合は、黙って片方に合わせません。どちらを正とするか判断し、コード・仕様・移行方法を整合させます。

## パイプライン全体

YouTubeの字幕・チャット・概要・事後コメントとXのTSVログから、しずくのFandom Wikiの紹介ページ・年表ページを更新する候補を作ります。

```text
S0 s0_intake     生ログを再帰探索しdata/raw/へ配置（info.txtの動画ID・投稿日を正とする）
S1 s1_normalize  決定的正規化 → data/normalized/（sentences/chat/signals/meta）＋X月別JSONL
S2 s2_pack       抽出パック生成 → LLM①抽出 → s2_ingest / s2_batchでカードJSONLを検証取込
S3 s3_match      台帳照合パック生成 → LLM②判定 → --ingestで判定取込・クローズ提案
S4 s4_packet     レビューパケット生成 → 人間が試聴・チェック
S5 s5_apply      チェック結果を反映 → handoff生成 → LLM③Wiki起草 → 人間が公開
doctor          本流とは別のデータ不備検査
```

LLMを使うのは①抽出、②照合判定、③承認後のWiki起草の3か所だけです（`MANUAL.md` §4）。それ以外は決定的スクリプトで処理します。

## 変更禁止の原則

1. ASR/OCR由来の文章を機械的に逐語確定しません。人間が試聴するまで `verbatim=false` を維持します。
2. 壊れたASRを推測で `text` に復元しません。必要なら `guess` に限定します。
3. `data/raw/`、正規化データの `asr` 列、チャット原文、X原文を変更しません。辞書補正は `norm` 列だけです。
4. 日付、数値、固有名詞、話者が不確かなカードを作りません。相対日付から出来事の日を逆算しません。
5. 決定的な正規化・集計・照合をLLMへ移しません。LLMは新規単位の抽出、短い照合判定、承認後のWiki起草だけに使います。
6. 逐語確認、公開、辞書・スキーマ変更、ループ確定、月次棚卸しの5つの人間ゲートを迂回しません。
7. カードID、ref名、`match_seen.json` のペアID方式を、移行スクリプトと検証なしに変更しません。
8. OCRチャット由来のカードを逐語扱いにしません。アーカイブ再アップの日付補正も維持します。
9. handoffのソースタイトルを保持します。S5はYouTube配信のタイトル（`meta.json`）とX投稿本文の冒頭を各ブロックへ付けます。Wikiの出典表記に必要なため、この付与を外しません。

## 環境

- Python 3.9以上、標準ライブラリのみです。この配下へ外部パッケージを追加しません。
- Windows利用を前提に、UTF-8、CRLF/BOM、Unicodeパス、長いパスへ配慮します。
- ネットワークやFandom APIを前提にしません。Wikiのソースは人間が渡し、公開操作は人間が行います。
- コマンドはこの `tools/shizuku-pipeline/` をカレントディレクトリにして実行します。
- ドキュメントのPythonコマンドは `python` で統一します。実環境により `py` / `python3` を使います。
- bashがdash相当の環境もあるため、brace展開へ依存する処理は避け、スクリプトはPythonに寄せます。

## データの扱い

再生成できる `data/raw/`、`data/normalized/`、`data/packs/` はコミットしません。一方、LLMの生出力、人間の判断、カード庫、台帳、handoff、進捗状態、設定は再生成不能または履歴として重要です。

特に次は安易に削除・再生成・上書きしません。

- `data/llm_out/`
- `data/cards/`
- `data/ledger/`
- `data/review/`（自動生成の `doctor_report.md` を除くレビュー記録）
- `data/handoff/`
- `data/state/`
- `config/`

状態ファイルを削除すると重複処理やレビュー漏れにつながります。`--apply`、`--reset`、取り込み系コマンドは、対象と差分を確認してから使います。

主な状態ファイル（`data/state/`）:

| ファイル | 意味 |
|---|---|
| `manifest.json` | S1処理済みの配信 |
| `desc_lines.json` | 概要欄の既知行。新規行検知の基準 |
| `extracted.json` | S2抽出済み。キーは `stream:<vid>` / `x:<month>` |
| `match_seen.json` | 照合済みペアID `loop_id__card_id`。カードIDではなく、処理順に依存しない照合に必要 |
| `in_review.json` | S5で処理済みのカード・ループID。パケット掲載だけでは登録しない |

## 実装時の注意

- パーサー変更ではSBV、SRT、`*.srt.txt`、負時刻チャット、OCRチャット、空記録、アーカイブ再アップを考慮します。
- `evidence` と `wiki_target` は文字列リストとして正規化します。古いデータの互換性を壊しません。
- 新しいフィールドやenumは `docs/SPEC.md`、プロンプト、取込、カード保存、レビュー出力をまとめて更新します。
- `config/asr_fixes.tsv` へ曖昧な断片を追加しません。条件は `DATA-ISSUES.md` §2に従います。
- プロンプト変更はサンプルだけで判断せず、既存データで再現率、誤検出、警告数を比較します。
- 大量データでは `--until`、`--max-pairs`、`--kinds`、`--limit` で処理を分割します。
- カードIDは `{base}-{kind[:2]}{sha8(kind+body)[:6]}` です（base例: `yt-<vid>-t<秒>` / `x-<postid>`）。変更すると重複判定・台帳リンク・パケット照合が壊れるため、移行スクリプトが必要です。
- S3の照合は期間と件数で区切ります。`--max-pairs` の既定は1500です。万単位のペアを一度にLLMへ判定させません。
- S4の `--reset` は処理済み候補を再レビュー対象へ戻す場合だけ使います。未処理候補はパケットを作り直すたびに再出現します。
- S5は `[x]` 行だけを処理し、`[ ]` 行は保留します。年表だけを先に適用し、名言を後日 `s4_packet --kinds quote` で再生成して続けられます。適用済みパケットは再利用しません。パケットの `補足:` はhandoffへ転記します。
- 抽出は1配信につき1チャットです。同じ配信の全partは同じチャットへ順番に渡し、別配信は混ぜません（動画ID・秒数の混同を避けるため。`MANUAL.md` Step2b）。
- Wikiは公開物であるため、子ども関連を含む安全性への配慮を維持します。

## 安全な確認コマンド

```powershell
# 構文確認
python -c "import glob, py_compile; [py_compile.compile(f, doraise=True) for f in glob.glob('scripts/*.py')]"

# 状態確認（永続データを変更しない）
python scripts/s2_pack.py --status
python scripts/s3_match.py --status
python scripts/s3_match.py --list-open
python scripts/s2_batch.py --status
python scripts/repair_cards.py

# 取り込み前の下見
python scripts/s0_intake.py --src <リポジトリのlogsフォルダ> --dry-run
```

`python scripts/doctor.py` は診断に有用ですが、`data/review/doctor_report.md` を上書きします。必要な診断として実行した場合だけ、その差分をレビューします。

振る舞いを変えたときは、構文確認に加えて影響する最小データで一巡させ、`docs/PLAN.md` の回帰基準または変更前の結果と比較します。本番データへ適用するコマンドは、明示的に依頼された範囲でのみ実行します。

## 運用コマンド（状態更新を伴う）

以下は下見用の一括実行リストではありません。依頼された工程だけを実行し、人間ゲートは維持します。全体の手順は `MANUAL.md` §2 Step0〜Step5です。

```powershell
# 取り込み〜正規化（先にs0_intakeの--dry-runで確認）
python scripts/s0_intake.py --src <リポジトリのlogsフォルダ>
python scripts/s1_normalize.py --all

# 抽出パック → LLM① → 同名.jsonlをdata/llm_out/へ保存 → 一括取込
python scripts/s2_pack.py --all
python scripts/s2_batch.py --apply
# 1パックずつ取り込む場合。Xの--fromは "x:<YYYY-MM>"
python scripts/s2_ingest.py --file data/llm_out/<pack名>.jsonl --from "stream:<vid>"

# 照合パック → LLM② → 判定の取込
python scripts/s3_match.py --until <YYYY-MM-DD> --max-pairs 1500
python scripts/s3_match.py --ingest data/llm_out/<judgments>.jsonl

# レビュー用パケット → 人間が試聴・チェック → handoff → LLM③
python scripts/s4_packet.py --mature-days 30 --until <YYYY-MM-DD> --kinds event,quote --limit <件数>
python scripts/s5_apply.py --packet data/review/<RV_xxxx.md>

# 修復・やり直し（通常運転では実行しない）
python scripts/s3_reset.py --apply
python scripts/repair_cards.py --apply
```

S2は全パックのJSONLをそろえてから一括取込するのが推奨です。`s2_batch` の引数なし実行はドライラン、`s3_reset` の引数なし実行は表示のみです。S4の期間・種類・件数はレビュー可能な範囲に区切ります。

## 過去の回帰基準とタスクの入口

以下は配信4本＋Xログ2641件で検証した時点の目安です。現在の状態は `docs/PLAN.md`、契約は `docs/SPEC.md` を確認し、下記を現在値と混同しません。

- 7-24配信（SBV）: 1199ブロック→808文、辞書99箇所、あき先生22件・秋先生0件（`norm` 列）。
- 8-02配信: ミスマッチ先頭36:40〜37:20（非言語音イベント）。
- X月別: 2026-01:233 / 02:1148 / 03:773 / 04:396 / 05:91。UTC→JSTの日付ずれ234件。
- 台帳デモ: ギャルボイス願望（X 2026-02-28）→ギャル配信（2026-05-24）で回収成立（`closed.jsonl`）。
- doctor: ERROR 0 / WARN 5〜6 / INFO 18〜31。既知のWARNは辞書残存報告と空の `2025.txt`。

データ不備は必要な場合だけdoctorを実行して `DATA-ISSUES.md` の該当節へ進みます。プロンプト改善は `prompts/extract_stream.md` と既存Wikiの2026年分でバックテストし、`docs/ROADMAP.md` の評価手順に従います。モデル比較では `s2_ingest` の警告数・再現率・誤検出を採点に使います（`MANUAL.md` §4末尾）。モデルBへの移行も `docs/ROADMAP.md` に従い、S5の試聴・採否・貼付は人間に残します。

## 完了条件

- コード、`docs/SPEC.md`、操作手順、プロンプトの契約が一致している。
- 人間ゲートや逐語性を弱めていない。
- 再生成不能データとユーザーの既存差分を壊していない。
- 実行した検証、更新された状態ファイル、残る警告を報告できる。
