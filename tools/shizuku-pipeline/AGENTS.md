# AGENTS.md — shizuku-pipeline

このファイルは `tools/shizuku-pipeline/` 以下に適用され、ルートの `AGENTS.md` を補足します。このパイプラインは、ログからWiki更新候補を生成する半自動システムです。最終判断と公開は人間が行います。

## 必読順

1. `CLAUDE.md` — エージェント向けの詳細な引き継ぎと運用上の注意
2. `docs/ARCHITECTURE.md` — 設計思想と境界
3. `docs/SPEC.md` — スキーマ、ID、状態遷移、CLIの契約
4. 作業内容に応じて `MANUAL.md`、`DATA-ISSUES.md`、`docs/PLAN.md`、`docs/ROADMAP.md`

実装と文書が食い違う場合は、黙って片方に合わせません。どちらを正とするか判断し、コード・仕様・移行方法を整合させます。

## 変更禁止の原則

1. ASR/OCR由来の文章を機械的に逐語確定しません。人間が試聴するまで `verbatim=false` を維持します。
2. 壊れたASRを推測で `text` に復元しません。必要なら `guess` に限定します。
3. `data/raw/`、正規化データの `asr` 列、チャット原文、X原文を変更しません。辞書補正は `norm` 列だけです。
4. 日付、数値、固有名詞、話者が不確かなカードを作りません。相対日付から出来事の日を逆算しません。
5. 決定的な正規化・集計・照合をLLMへ移しません。LLMは新規単位の抽出、短い照合判定、承認後のWiki起草だけに使います。
6. 逐語確認、公開、辞書・スキーマ変更、ループ確定、月次棚卸しの5つの人間ゲートを迂回しません。
7. カードID、ref名、`match_seen.json` のペアID方式を、移行スクリプトと検証なしに変更しません。
8. OCRチャット由来のカードを逐語扱いにしません。アーカイブ再アップの日付補正も維持します。

## 環境

- Python 3.9以上、標準ライブラリのみです。この配下へ外部パッケージを追加しません。
- Windows利用を前提に、UTF-8、CRLF/BOM、Unicodeパス、長いパスへ配慮します。
- ネットワークやFandom APIを前提にしません。Wikiのソースは人間が渡し、公開操作は人間が行います。
- コマンドはこの `tools/shizuku-pipeline/` をカレントディレクトリにして実行します。

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

## 実装時の注意

- パーサー変更ではSBV、SRT、`*.srt.txt`、負時刻チャット、OCRチャット、空記録、アーカイブ再アップを考慮します。
- `evidence` と `wiki_target` は文字列リストとして正規化します。古いデータの互換性を壊しません。
- 新しいフィールドやenumは `docs/SPEC.md`、プロンプト、取込、カード保存、レビュー出力をまとめて更新します。
- `config/asr_fixes.tsv` へ曖昧な断片を追加しません。条件は `DATA-ISSUES.md` §2に従います。
- プロンプト変更はサンプルだけで判断せず、既存データで再現率、誤検出、警告数を比較します。
- 大量データでは `--until`、`--max-pairs`、`--kinds`、`--limit` で処理を分割します。

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

## 完了条件

- コード、`docs/SPEC.md`、操作手順、プロンプトの契約が一致している。
- 人間ゲートや逐語性を弱めていない。
- 再生成不能データとユーザーの既存差分を壊していない。
- 実行した検証、更新された状態ファイル、残る警告を報告できる。
