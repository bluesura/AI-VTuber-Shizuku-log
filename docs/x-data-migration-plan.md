# Xログ 統合データ修正・移行計画（Phase 1〜4）

2026年11月25日に実施した `fxtwitter-skill` による全4,266件照合結果と、既存Xログ（`2023.txt`〜`202601-05.txt`）の品質監査に基づき、XログをWiki・辞書系サイト反映に耐えうる状態へ整備するための段階的計画です。

---

## 背景と主な修正対象（2026-11-25 監査結果より）

1. **本文誤帰属・エラーの修復（最優先）**
   - 旧DOM抽出ログにおいて、引用元の本文がしずく本人の `本文` 欄に誤混入していた7件（例：`1639175270040211456`）、および `#ERROR!` 表記になっていた1件（`2017453526180372925`）を修復する。
2. **欠落テキスト・絵文字・URLの復元**
   - 本文空欄47件のうち46件で FxTwitter から絵文字等の本文が取得済み。
   - 標準絵文字の抜け落ち（例：2023年ログ `id=1568` の推しマーク欠落等）、120文字での引用文途切れ、`t.co` 未展開・省略URLを復元する。
3. **スキーマ統一と肥大化抑制**
   - `id`（連番）列の揺れを廃止し、`post_id` 主キーへ統一（URLは `/i/status/{post_id}` で生成）。
   - `source_method` / `quality_flags` / `metrics_date` を導入し、改行コードをLFへ統一、日時順に整列する。
4. **パイプライン・検証ツール側の注意点**
   - `fxtwitter-skill` のページ連結処理では途中でHTTP 404が発生してもJSONの `code` が最初の `200` のまま残るため、自動収集スクリプトではページ単位のHTTPステータス検査を必須とする。
   - `tools/shizuku-pipeline/scripts/s1_normalize.py` および `doctor.py` は現在 `URL` 列を前提としているため、`post_id` 対応へ更新する。

---

## 実行フェーズ

### Phase 1：スキーマ・匿名化ルールの確定（合意済み）
- **確定事項**:
  - `docs/x-log-spec.md` の新列定義を採用する（`post_id` 主キー、`/i/status/{post_id}` 生成）。
  - 一般視聴者への `REPLY` では、**相手の発言内容は保存せず、`reply_to_author` を `User_XXXXXXXX` へ匿名化した上で、文脈確認用の導線として `reply_to_post_id` を保持する**。
  - 既存の過去4,266件は、保存済みの FxTwitter 応答を使って一括修復し、`source_method=web_dom+fx` へ書き換える。
  - `likes` / `reposts` / `replies` の空欄は旧データについて `count_uncertain` フラグで明示し、反応数の基準日を `metrics_date`（旧ログは `2026-05-22`）として保持する。
  - `tools/scripts/anon_whitelist_x.txt` に、`@cumulo_autumn`、`@Nya6y`、コラボ相手VTuber等を定義する。

### Phase 2：既存4,266件の一括クレンジング＆FxTwitter補完（ローカル完結）
- **入力**:
  - 移行前の旧形式TSVの控え（`2023.txt`, `2024.txt`, `202601-05.txt`）。再実行時は控えのディレクトリを `--src-dir` に指定する。
  - 検証時に保存済みの `outputs/fxtwitter-audit/responses/status_<post_id>.json`
- **実行スクリプト**: `tools/shizuku-pipeline/scripts/reconstruct_x_from_fxtwitter.py`
- **処理内容**:
  - `post_id` 主キー化、LF改行統一、`date_utc` 順ソート。
  - FxTwitterの `raw_text.display_text_range` と `facets` を用いて、絵文字を含む正確な本文・展開済みURLを復元。
  - 引用元誤混入7件および `#ERROR!` 1件を自動修正し、`quality_flags` に `dom_swapped_fixed` / `error_fixed` を記録。
  - `quote_post_id`・`quote_author`・`quote_text` を補完。
  - `reply_to_post_id`・`reply_to_author` を設定（一般視聴者は `User_XXXXXXXX` 化し、相手本文は保存しない）。
  - メディアURLの `name=small` 等を `name=orig` へ正規化。
  - `source_method` を `web_dom+fx` に設定し、反応数は元の `2026-05-22` を維持（`metrics_date=2026-05-22`、`snapshot_date=2026-11-25`）。
  - ※2023-05-24 `1661325152653815808`（`雖後□...`）のような演出上の文字化けは原文のまま保持する。

### Phase 3：欠損している返信先（701件）の補完と匿名化
- **対象**: `type=REPLY` のうち `status` 応答で `replying_to` が `null` だった701件、および親投稿IDが未取得の行。
- **処理内容**:
  - FxTwitter の `thread` / `conversation` エンドポイントへバッチ問い合わせを行い、`reply_to_post_id`・`reply_to_author` を補完する（該当行の `source_method` は `fx_thread` 併用を記録）。
  - ホワイトリスト判定を通し、一般視聴者は `User_XXXXXXXX` へ匿名化する。
  - なお取得できなかった行には `quality_flags` に `missing_parent` を残す。

### Phase 4：カバレッジ補完とパイプライン追従改修
- **未収録期間の点検（2023年4月〜11月）**:
  - 2023年3月（1,513件）に対し4〜11月が各月0〜18件と極端に少ないため、YouTube配信実施日（計49回）の告知ポスト有無や、削除・API制限による欠落状況を調査し、`docs/archive-policy.md` に記録する。未収録ポストが見つかった場合は「WebでID回収 → FxTwitterで確定」の2段階で追記する。
- **周辺アカウントの追加と定期収集**:
  - `@cumulo_autumn` の新規収集パイプライン追加（`type=RETWEET` は除外または分離）。
  - `@Nya6y` のアーカイブ断片（Wayback / togetter / 引用RT等）を別枠または出典明記の上で整理。
  - 定期実行によるID収集 → FxTwitter `status` 確定のワークフローを整備する。
- **パイプライン改修**:
  - `tools/shizuku-pipeline/scripts/s1_normalize.py`（`process_x()`）および `doctor.py` を新スキーマ（`post_id`、`quote_post_id`、`quality_flags`、`RETWEET` 除外）に対応させる。
  - 今後の定期収集スクリプトでは、`fxtwitter-skill` のページ連結ではなく自前でページ単位のHTTPステータスを検査して `404` 誤判定を防ぐ。
