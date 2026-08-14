# CLAUDE.md — AIエージェント引き継ぎガイド

このファイルは、このリポジトリ（`shizuku-pipeline`）を引き継ぐAIエージェント（Claude Code等）向けの操作指針です。
人間向けの手順書は `MANUAL.md`、設計思想は `docs/ARCHITECTURE.md`、正確な仕様は `docs/SPEC.md` にあります。
**まず本ファイルと `docs/ARCHITECTURE.md` を読んでから作業を始めてください。**

## これは何か（30秒）

AI VTuber「しずく」の Fandom wiki（**紹介ページ**＝機能・スペック紹介、**年表ページ**＝出来事の時系列）を、
蓄積したログ（YouTube配信の字幕/チャット/概要/事後コメント、XのTSVログ）から**半自動で更新する**ためのパイプライン。
完全自動ではなく、**人間の承認ゲートを通してのみ**wikiに反映する。LLM（Claude）は3か所でだけ使う。

## 絶対に守る原則（これを壊す変更はしない）

1. **逐語はマシンが確定しない。** 字幕(ASR)由来のテキストは必ず `verbatim=false`。人間が試聴して確定するまで名言として採用しない（ゲート1）。壊れたASRを推測で「復元」してカード本文に書くことは禁止（`guess` フィールドには可）。
2. **決定的処理とLLMを分離する。** 文の再結合・辞書適用・JST変換・シグナル検出・照合の集計は**すべてスクリプト**（`data/normalized/` 以下、`grep`で追える）。LLMは「新規1単位の抽出」と「短い照合判定」だけ。
3. **推測で埋めない。** 日付・数値・固有名詞に確信が持てないものはカードにしない。相対日付（「先週」等）から逆算しない。
4. **原文を壊さない。** `data/raw/` と正規化の `asr` 列、チャット原文、Xlog原文は不変。辞書補正は `norm` 列にのみ適用し、チャット/Xには絶対に適用しない。
5. **5つの人間ゲートを迂回しない。** ①逐語(VERIFY) ②公開(ADOPT→wiki貼付) ③辞書・スキーマ変更 ④ループ確定(CLOSE) ⑤月次棚卸し。スクリプトはゲートの手前で止まり、判断を人間に残す。

## 環境と制約

- **Python 3.9+、標準ライブラリのみ。** 追加パッケージを導入しない（`pip install` を増やさない）。移植性が要件。
- コマンドは `python`（環境により `py`/`python3`）。ドキュメントは `python` で統一。
- OSは Windows 主体（ユーザー環境）。パス区切り・文字コード・パス長260字制限に注意。全パーサはCRLF/BOMを吸収済み。
- ネットワーク前提なし。Fandomは `web_fetch` が402で拒否されるため、wikiソースは**人間が貼る**設計（`prompts/draft_wiki.md`）。

## パイプライン全体（8ステップ）

```
S0 s0_intake     生ログを再帰探索し data/raw/ に配置（info.txtの動画ID・投稿日を正とする）
S1 s1_normalize  決定的正規化 → data/normalized/（sentences/chat/signals/meta）＋ X月別jsonl
S2 s2_pack       抽出パック生成（→ Claudeチャット①）  / s2_ingest でカードJSONLを検証取込
S3 s3_match      台帳照合パック生成（→ Claudeチャット②）/ --ingest で判定取込→クローズ提案
S4 s4_packet     レビューパケット生成（人間が試聴・チェック）
S5 s5_apply      チェック結果を反映 → handoff生成（→ Claudeチャット③でwiki差分）
doctor           データ不備の独立検査（本流と別トラック）
```

Claudeチャットを開くのは **①抽出 ②照合判定 ③wiki起草** の3か所だけ（`MANUAL.md` §4）。
それ以外はすべて決定的スクリプト。

## よく使うコマンド

```bash
# 取り込み〜正規化
python scripts/s0_intake.py --src <リポジトリのlogsフォルダ> --dry-run   # まず下見
python scripts/s0_intake.py --src <...>                                   # 本実行
python scripts/s1_normalize.py --all

# 抽出（①）
python scripts/s2_pack.py --status                 # 進捗一覧
python scripts/s2_pack.py --all                    # 未抽出を一括生成 + data/packs/WORKLIST.md
python scripts/s2_ingest.py --file data/llm_out/<pack名>.jsonl --from stream:<vid>|x:<YYYY-MM>
python scripts/s2_batch.py [--apply]               # llm_out を一括取込 + WORKLISTチェック自動更新（推奨）
#   ↑ 全パックのJSONLを llm_out に全部揃えてから一括、が効率的。1本ずつは上の s2_ingest。

# ↑ Step2の推奨ワークフロー: s2_pack --all → (各パックをClaudeへ, 返答を llm_out に同名.jsonlで保存) → s2_batch --apply

# 照合（②）→ パケット → 反映（③）
python scripts/s3_match.py --status                # 未回収ループ・カード数・月別分布
python scripts/s3_match.py [--until YYYY-MM-DD] [--max-pairs N]   # 照合パック（既定1回1500ペア上限）
python scripts/s3_match.py --ingest data/llm_out/<judgments>.jsonl
python scripts/s3_match.py --list-open             # 未回収台帳
python scripts/s3_reset.py [--apply]               # 照合済み記録をリセット（大量実行後のやり直し）
python scripts/s4_packet.py [--mature-days 30] [--until YYYY-MM-DD] [--kinds event,quote,...] [--limit N] [--reset]
python scripts/s5_apply.py --packet data/review/RV_xxxx.md

# 健診
python scripts/doctor.py                           # → data/review/doctor_report.md
python scripts/repair_cards.py [--apply]            # 壊れたカード(evidence等が非文字列)の修復
```

## データの置き場と意味

| パス | 内容 | git | 再生成 |
|---|---|---|---|
| `data/raw/` | 生ログのコピー＋`origin.json` | ✗上げない | s0で可 |
| `data/normalized/` | 文・チャット・シグナル・X月別 | ✗上げない | s1で可 |
| `data/packs/` | Claude添付用パック＋WORKLIST | ✗上げない | s2で可 |
| **`data/llm_out/`** | **Claudeの生出力（JSONL）** | **✓上げる** | **不可** |
| `data/cards/` | 検証済みカード庫（月別JSONL）＝**Card Store** | ✓上げる | 不可 |
| `data/ledger/` | 台帳 open/closed/proposals | ✓上げる | 不可 |
| `data/review/` | レビューパケット（人間の試聴記録）※doctor_report.md除く | ✓上げる | 不可 |
| `data/handoff/` | wiki起草チャットへの受け渡し | ✓上げる | s5で可 |
| `data/state/` | 進捗（下記） | ✓上げる | 不可 |
| `config/` | 辞書・語彙・機能レジストリ・既知不在・配信関係 | ✓上げる | 不可 |

状態ファイル（`data/state/`）:
- `manifest.json` … s1処理済みの配信
- `desc_lines.json` … 概要欄の既知行（新規行検知の基準線）
- `extracted.json` … s2抽出済み（キー `stream:<vid>` / `x:<month>`）
- `match_seen.json` … **照合済みペアID**（`loop_id__card_id`。カードIDではない。順序非依存のため）
- `in_review.json` … パケット掲載中のカード/ループID

## 変更するときの注意（ここでミスが起きやすい）

- **ID体系を変えない。** カードID `{base}-{kind[:2]}{sha8[:6]}`（base例 `yt-<vid>-t<秒>` / `x-<postid>`）。IDが変わると重複判定・台帳リンク・パケット照合が全部壊れる。変える場合は移行スクリプトを用意。
- **Step5は種別ごとに途中まで適用してよい。** `s5_apply` は `[x]` 行だけ処理し `[ ]` は無視。年表だけチェックして適用→名言は後日 `s4_packet --kinds quote` で作り直して続行、が正しい進め方。未処理候補は失われず何度でも再出現する。適用済みパケットは再利用しない。
- **Step4(パケット)も大量候補では区切る。** `--until`/`--kinds`/`--limit` で分割レビュー。未処理候補は作り直すたび何度でも出る（処理済みだけ外れる）。`--reset`は処理済みを再レビュー対象に戻す時のみ。パケットの `補足:` 行はhandoffに転記される。
- **Step3は大量データでは区切る。** 過去ログ一括抽出で未回収ループが数百〜数千になると照合ペアが万単位に膨れる。`--until`（期間）と `--max-pairs`（既定1500）で刻む。万単位のパックをLLMに判定させない（`MANUAL.md` Step3）。
- **`match_seen.json` はペアID。** 「照合済みカード」に戻すと、後から開いたループが既存カードと結びつかず回収を取りこぼす（この設計判断は `docs/ARCHITECTURE.md` の「照合の順序非依存」参照）。
- **辞書 `config/asr_fixes.tsv` に曖昧な断片を足さない**（ゲート3）。追加条件は `DATA-ISSUES.md §2`。チャット/Xには適用しないこと。
- **アーカイブ再アップの日付補正を壊さない。** `config/stream_relations.tsv` の `archive_of` により s2_ingest がカード日付を元配信日へ補正する。これが無いと年表の日付が再アップ日で誤る（`DATA-ISSUES.md §14`）。
- **OCRチャット（`*.live_chat_ocr.txt`）由来は逐語不可。** s2_ingest が機械的に `verbatim=false` に落とす。この防御を外さない（`DATA-ISSUES.md §13`）。
- **evidence/wiki_target は必ず文字列リスト。** LLMが dict で返すことがある。取込時に `as_str_list` で正規化済みだが、古いデータで s3/s4 が落ちたら `python scripts/repair_cards.py --apply` で修復する。
- **抽出は1配信=1チャット。同一配信の全partは同じチャットで順番に、別配信は別チャットに。** 別配信を混ぜると動画ID・秒数が混ざったカードが出る（`MANUAL.md` Step2b）。
- **bashは環境によりdash。** brace展開が使えないことがある。スクリプトはPythonに寄せる。
- **変更後は必ず**: `python -c "import py_compile,glob;[py_compile.compile(f,doraise=True) for f in glob.glob('scripts/*.py')]"` で全構文チェック → 可能なら実データで一巡。

## 検証済みの実測値（回帰の基準線）

`docs/PLAN.md` に現況、`docs/SPEC.md` に契約。以下は「壊れていないこと」の目安（配信4本＋Xログ2641件時点）:
- 7-24配信 `[sbv]`: 1199ブロック→808文、辞書99箇所、あき先生22/秋先生0（norm列）。
- 8-02配信: ミスマッチ先頭 `36:40〜37:20`（非言語音イベント）。
- Xログ月別: 2026-01:233 / 02:1148 / 03:773 / 04:396 / 05:91。UTC→JST日付ずれ 234件。
- 台帳デモ: ギャルボイス願望(X 2026-02-28) → ギャル配信(2026-05-24) で回収成立（`closed.jsonl`）。
- doctor: ERROR 0 / WARN 5〜6 / INFO 18〜31（WARNは辞書残存報告と2025.txt空記録＝理解済み）。

## タスク別の入口

- **新しい配信を処理**: `MANUAL.md` §2 Step0→Step5 を順に。
- **データ不備を調べる**: `python scripts/doctor.py` → `DATA-ISSUES.md` の該当§。
- **プロンプトを改善**: `prompts/extract_stream.md` を編集 → 既存wiki2026年分でバックテスト（`docs/ROADMAP.md`「評価」）。
- **モデル比較**: `s2_ingest` の⚠件数・再現率・誤検出を採点表として使う（`MANUAL.md` §4末尾）。
- **Model Bへ移行**: `docs/ROADMAP.md`。S0〜S4を自動化し、S5（試聴・採否・貼付）だけ人間に残す。

## してはいけないこと（要約）

- 逐語未確定の名言をwikiに出す / ASRを推測復元して本文に書く。
- 決定的処理をLLMに肩代わりさせる（集計・照合・正規化）。
- `data/raw/` や `asr`列・チャット原文・Xlog原文を書き換える。
- 追加パッケージ導入・ID体系変更・ゲート迂回を、移行と検証なしに行う。
- 子ども関連その他の安全性に関わる配慮を欠いた出力（wikiは公開物である点に留意）。
