# SPEC.md — 仕様（契約）

正確な定義集。実装と食い違ったら、実装を直すか本書を直すかを明示的に決めること。
思想は `ARCHITECTURE.md`、手順は `MANUAL.md`。

## 1. カード スキーマ

1行1JSON（JSONL）。共通フィールド:

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `kind` | enum | ✓ | `event` / `quote_candidate` / `open_loop` / `capability` / `profile_fact` / `stream_note` |
| `date_jst` | `YYYY-MM-DD` | ✓ | 出来事の日付（JST）。配信日 or ポスト日。相対表現から逆算しない |
| `source` | object | ✓ | 下記 |
| `text` | string | ✓* | 本文。掛け合いは `parts` を使い `text` は省略/null可 |
| `verbatim` | bool | ✓ | 逐語として引用可能か。ASR由来は常に false |
| `summary` | string | ✓ | 一文要約（年表等に使う） |
| `wiki_target` | string[] | ✓ | 書き込み先の節（例 `["年表"]`, `["名言・迷言"]`, `["台帳"]`, `["しずくの配信"]`） |
| `salience` | object | ✓ | 反響の手がかり（`chat_burst`, `comment_ref`, `likes`, `views` 等、任意キー） |
| `evidence` | string[] | ✓ | 根拠（チャット引用など、時刻付き）。LLMがdict等で返しても取込時に文字列リストへ正規化（非文字列も受理） |
| `id` | string | 自動 | 取込時に付与（§4） |
| `status` | enum | 自動 | `candidate`→`verified`→`approved` / `rejected`（§5） |

`source` オブジェクト:
- YouTube: `{"type":"yt","video_id":"<11桁>","t":<秒>,"url":"https://www.youtube.com/live/<vid>?t=<秒>"}`
- X: `{"type":"x","post_id":"<id>","url":"https://x.com/.../status/<id>"}`

kind別の追加フィールド:
- `open_loop`: `loop_type`（§2の7種）必須、`expected_signal`（回収条件・一文）必須、`antecedent_hint`（過去参照のみ・過去ログ探索の手がかり）任意。
- `capability`: `feature_hint`（機能の仮名称）。`evidence` にチャット反応を必ず入れる。
- `quote_candidate`（掛け合い）: `parts: [{"speaker":"ご主人様のコメント"|"しずく","text":...,"verbatim":bool}, ...]`。ご主人様側はチャット原文を一字一句コピー。
- ASR由来で本文が壊れている場合: `text` はASR表示のまま、`guess`（復元案）に人間の試聴補助として推測を書いてよい（`text` には書かない）。
- アーカイブ再アップ取込時に自動付与: `upload_date`（元の投稿日。`date_jst` は元配信日に補正済み）。
- S3 relatedで自動付与: `links: [loop_id, ...]`。

## 2. 台帳（ledger）スキーマ

`open.jsonl` / `closed.jsonl` の1行:
```
{"loop_id","opened":"YYYY-MM-DD","loop_type","text","expected_signal",
 "antecedent_hint"?,"source":{...},"status":"open"|"closed"|"dropped",
 "closed"?:"YYYY-MM-DD","closed_by"?:"<card_id>","dropped"?:"YYYY-MM-DD"}
```
`loop_type` ∈ {目標宣言, 願望, 不能表明, 予告・約束, 過去参照, 定型ネタ, 関係マーカー}。

`proposals.jsonl`（クローズ提案）の1行:
```
{"loop_id","card_id","confidence":0.0-1.0,"reason":"一文"}
```

## 3. 設定ファイル（config/）

すべてTSV。`#` 始まりと空行は無視。

- `asr_fixes.tsv`: `誤記<TAB>正<TAB>備考`。**normalized の norm 列にのみ適用**。追加条件は「誤記側がこの文脈で正表記以外を意味しない」（ゲート3）。曖昧な断片は入れない。チャット/Xには適用しない。
- `lexicon.tsv`: `family<TAB>カンマ区切りキーワード`。signals の語彙群ヒント用。
- `features_registry.tsv`: `feature_id<TAB>名称<TAB>状態<TAB>備考`。capability新規判定の突合先。四半期棚卸しで更新。
- `known_absent.tsv`: `動画ID<TAB>種別(comments|chat|subs)<TAB>理由`。恒久的に存在しないデータの登録簿。doctor/s0の警告を抑止し理由を記録。
- `stream_relations.tsv`: `動画ID<TAB>関係(archive_of|part_of|reupload_of)<TAB>相手の動画ID<TAB>備考`。日付補正・関係表示に使う。

## 4. ID体系

- カードID: `{base}-{kind[:2]}{sha8(kind+body)[:6]}`
  - base: YouTube→`yt-<vid>-t<秒>`（秒不明は `t x`）、X→`x-<post_id>`
  - `kind[:2]`: `ev`/`qu`/`op`/`ca`/`pr`/`st`
  - body: `text` または `parts` のJSON
  - 例: `yt-fm2mzPJylCU-t2893-opb05010`
- 同一内容は同一IDになり重複取込は自動スキップ。**ID体系を変えると台帳リンク・重複判定・パケット照合が壊れる**（変更時は移行スクリプト必須）。
- refのname（wiki用、`prompts`/`s4`で生成）: `yt-<vid>-t<秒>` / `x-<post_id>`。

## 5. カードの状態遷移

```
candidate ──VERIFY(逐語確定)──▶ verified ──ADOPT──▶ approved ──▶ handoffに載る
    └────────────────ADOPT(event/capability等,逐語不要)─────────▶ approved
    └────────────────DROP───────────────────────────────────────▶ rejected
```
- `quote_candidate` は verified を経ないと approved にできない（S5が拒否）。
- approved のカードだけが handoff に出力される。

## 6. 状態ファイル（data/state/）

| ファイル | 型 | キー/内容 |
|---|---|---|
| `manifest.json` | dict | `{dir名: {"s1": true}}`（S1処理済み） |
| `desc_lines.json` | dict | `{概要欄の行: 初出vid}`（新規行検知の基準線） |
| `extracted.json` | dict | `{"stream:<vid>"\|"x:<month>": {"cards":n,"at":日付}}` |
| `match_seen.json` | **list** | 照合済み**ペアID** `["loop__card", ...]`（カードIDではない） |
| `in_review.json` | dict | `{card/loop id: パケットID}`（掲載中） |

削除すると再処理される（例: `manifest.json` を消すとS1が全配信を再処理）。

## 7. CLIリファレンス

```
s0_intake.py   --src <dir> [--dry-run] [--verbose]
s1_normalize.py --all | --stream <vid>
s2_pack.py     --all [--redo] | --stream <vid> | --x <YYYY-MM> | --status
               [--split N] [--max-chars 90000]
s2_ingest.py   --file <jsonl> --from stream:<vid>|x:<YYYY-MM>
s3_match.py    (引数なし=照合パック生成) | --ingest <judgments.jsonl> | --list-open
s4_packet.py   [--mature-days 30]
s5_apply.py    --packet <RV_*.md>
doctor.py      (引数なし)
```

## 8. パック／パケット／handoff の形式

- **抽出パック** `data/packs/extract_<date>_<vid>.txt`（分割時 `_partN`）/ `extract_x_<month>.txt`:
  プロンプト＋配信固有の注意＋シグナル＋タイムライン（`[S mm:ss] 発話` と `[C mm:ss xxxx] チャット` を時系列統合）。
  上限 `--max-chars`（既定90000）超で自動分割。
- **LLM出力の保存名（規約）**: 添付パックと同じ名前で拡張子だけ `.jsonl` にし `data/llm_out/` に置く。
  名前がずれても `s2_ingest` は `--from` のIDから自動検出する。
- **照合パック** `data/packs/match_<date>.txt`: プロンプト＋ペアJSONL。
- **レビューパケット** `data/review/RV_<YYYYMMDD>-NN.md`: セクションA〜F。
  チェック規約: `- [x] ACTION <id>` の行だけ実行。未チェック＝保留（次回再掲）。
  アクション: `ADOPT` / `VERIFY`（直後の `逐語:` 行を本文化）/ `DROP` / `KEEP` / `CLOSE <loop_id> BY <card_id>`。
  名言は VERIFY で `逐語:` を書いてから ADOPT（ゲート1）。
- **handoff** `data/handoff/handoff_<packet>.txt`: 承認済みのみ。
  年表は3行形式【日付】【出来事の概要】【ソースURL】、名言は逐語＋出典、回収成立は括弧書き追補の材料、機能・人物は加筆材料。

## 9. wiki出力の書式（スキル側が最終権威）

`prompts/draft_wiki.md` の手順で `shizuku-wiki.skill` を併用したチャットに渡す。以下は下敷き:
- 年表行: `* YYYY-MM-DD：出来事<ref name="...">[URL タイトル]（媒体、YYYY年M月D日）</ref>`（コロンは全角、体言止め禁止、日付はゼロ埋めなし）。
- 名言: 【発話者】を明示、t付きURLを出典、注釈は付けない。
- ref name: `yt-<vid>-t<秒>` / `x-<post_id>` / `媒体スラッグ-YYYYMMDD`。
- 出典保存: 使用URLを web.archive.org に保存（スキル §3-6）。

## 10. 字幕・チャット・Xの入力形式

- 字幕: SBV（`H:MM:SS.mmm,...` ブロック）/ SRT・VTT（`-->` タイムコード）。SBV優先、無ければSRT。SRTのローリング重複は前方一致差分で吸収。
- チャット: `[H:MM:SS] @User_xxxx: 本文`（負時刻=開始前）。OCR復元は `@` が空でも解釈可、時刻は粗い。
- 事後コメント: `[YYYY-MM-DD ... UTC] @User（👍 n）` ヘッダ＋本文。本文中の `mm:ss` をタイムスタンプ参照として抽出。
- info: `タイトル:` `投稿日:` `動画ID:` `URL:` ＋ 説明ブロック。
- Xログ: TSV。1行目に `URL`/`日付` 等のヘッダ。`日付` はUTC ISO8601 → S1でJST変換。本文/引用内容/いいね数/表示数等。「なし」のみのファイルは空記録として扱う。

## 11. gate一覧（迂回禁止）

| ゲート | 場所 | 内容 |
|---|---|---|
| ①逐語 | S5 VERIFY | 試聴して逐語確定。機械は verbatim=false に倒す |
| ②公開 | S5 ADOPT→貼付 | wikiへ出す前の人間承認 |
| ③辞書・スキーマ | config編集時 | 辞書追加条件・スキーマ変更の人間判断 |
| ④ループ確定 | S5 CLOSE | 回収成立の人間確認（S3は提案のみ） |
| ⑤月次棚卸し | 運用 | 名言選考(30日熟成)・台帳棚卸し・doctor・回帰確認 |
