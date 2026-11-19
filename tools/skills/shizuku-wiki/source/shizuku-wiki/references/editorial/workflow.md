# 文章品質ワークフロー

## 判断の順番

1. 現行Wikiソース・リビジョン、出典、ページ別ガイド、文体ガイドを確認する。データ行だけの機械更新は既存の手順を使う。
2. 年表は `page-timeline.md` §2-1に従い、各項目の種類・確認段階・しずくとの関係を整理してから、今回の追加・置換部分だけを初稿にする。視点にずれがあれば根拠に戻って構成を直す。
3. `page-profiles.md` で推敲の強度を選ぶ。推敲が必要な箇所は `yomiyasu-adapter.md` に従い、称号・名言・世界観は `style-exceptions.md` に従って保持する。
4. 最終稿を変更後の節に組み込み、前後の項目と対象ページのルールに照らして読む。年表は推敲しなかった行を含む全追加・置換項目を `page-timeline.md` §7で審査し、下記の記録を作る。
5. 形式と審査記録を検査してから、挿入位置付きのWiki差分を提示する。未解決の項目は公開候補から外し、保留理由を報告する。公開直前の再確認は `article-workflow.md` §5に従う。

## 形式保護と診断

以下はスキルフォルダを基準にした例。原稿・記録はGit管理外の `outputs/shizuku-wiki/<作業名>/` 等に置く。短いファイル名は作業ファイルのパスに読み替える。

```text
python -X utf8 scripts/editorial_pipeline.py prepare --input proposal_initial.wiki --out editable.json
python -X utf8 scripts/editorial_pipeline.py apply --input proposal_initial.wiki --segments editable.json --edits edits.json --out proposal_final.wiki
```

`editable.json` の候補から推敲が必要な地の文だけを選ぶ。`masked` 中の `⟦MW...⟧` は同じ順に残す。`edits.json` は `{"edits": {"L00001": "推敲後のmasked文字列"}}` 形式。事実の訂正が必要なら出典を確認し、初稿の工程へ戻る。

```text
python -X utf8 scripts/editorial_pipeline.py audit --page general --baseline proposal_initial.wiki --revised proposal_final.wiki --json-out audit.json
```

`audit` は日付・数値・保護要素等の形式上の差を検出する。警告は原典と差分に照らして確認し、重大な不一致を解決してから採用する。年表は下記のコマンドを使う。

`deslop-ja` は診断専用。`natural-japanese` の `paragraphs.py` は段落分割、`newfacts.py` はSudachiPy等がある場合の追加固有情報検査に使う。複雑なテンプレート・複数行の表やHTMLは個別に差分確認する。任意依存やPythonが使えないときは未実施を記録し、目視で照合する。

## 年表の審査記録

`proposal_final.wiki` は今回の**追加・置換後の全項目**（`* YYYY-MM-DD：…`）と必要な年見出しだけにする。既存の変更しない行、差分の `+`、挿入位置の説明は別に置く。同日の別件も一行ずつ書く。日付未確認の行は保留する。

```text
python -X utf8 scripts/editorial_pipeline.py timeline-template --input proposal_final.wiki --out timeline-review.json
```

テンプレートは未審査で生成される。初稿前の整理と `page-timeline.md` §7の審査結果を各項目に記入する。

| キー | 記入内容 |
|---|---|
| `kind` | `action_change`（行動・変化）、`demo`（試作・デモ）、`announcement`（開発側の発表）、`foundation`（活動の土台） |
| `stage` | `operational`（実運用・実施済み）、`demo`（デモで確認）、`prototype`（試作）、`announced`（発表のみ）、`not_applicable`（段階の区別が該当しない出来事） |
| `source_basis` | `locator`（URL・タイムスタンプ・参照ファイル等）と `fact`（確認できた事実と根拠の限界）の組 |
| `shizuku_event` | しずくに何が起きたか、またはしずくの活動の土台とどう関係するか |
| `perspective` | しずくの出来事を中心に記す `direct`、技術的な発表・開発を中心に残す `technical_exception` |
| `alternative` / `exception_reason` | 技術的例外の場合に必須。検討したしずく中心の別案と、その案では保てない事実の範囲や行為者 |
| `checks` | `viewpoint`（視点）、`factual_scope`（事実の範囲）、`granularity`（粒度）、`context`（前後・連動）の各 `status`（`pass` / `hold` / `pending`）と具体的な `reason` |
| `decision` | 全確認済みなら `pass`、未解決なら `hold`、未審査なら `pending` |

`id`・`text`・ハッシュは検査対象を特定する欄。提案本文を直したら、新しい名前でテンプレートを作り、変更箇所と文脈を再確認する。変わらない項目の判断は、本文と文脈の対応を確認してから引き継げる。ハッシュはUTF-8テキストとして読み込んだ内容（BOM除去・改行正規化後）から計算する。

```text
python -X utf8 scripts/editorial_pipeline.py audit --page timeline --baseline proposal_initial.wiki --revised proposal_final.wiki --timeline-review timeline-review.json --json-out audit.json
```

年表では `--page timeline` を明示する。推敲なしの場合はbaselineとrevisedに同じファイルを渡す。審査記録が未了なら終了コード1と `timeline_review.status: blocked` が返る。項目と理由を調べて解決してから公開提案に戻す。形式警告は別途確認する。

`record_valid` は全項目の記録がそろい、保留がなく、審査対象と本文が一致していることを示す。視点と事実の妥当性はAI/人間が原典と文脈に照らして判断する。ユーザーの公開承認は別途確認する。

Pythonを実行できない場合も同じ欄をMarkdown等で記録して最終稿との対応を手動で照合し、機械検査の未実施と理由を報告する。公開直前は `article-workflow.md` §5に従う。

## 通常モードと比較モード

- 通常は最終Wiki差分と必要な未解決事項を表示する。
- 推敲前後の比較を明示された場合だけ `audit` に `--compare-report comparison.md` を追加する。同一実行内の初稿・最終稿・差分・採否理由を提案部分に限って示す。
- 版間比較は同一モデル・同一現行ソース・同一資料で各版を別々に実行する。

受け入れ条件は `QUALITY-GATES.md` を参照する。
