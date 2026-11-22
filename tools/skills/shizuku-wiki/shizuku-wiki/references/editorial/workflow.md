# v2 文章品質ワークフロー（公開前のローカル文章工程）

## 判断の順番

1. 対象ページの現行Wikiソースとrevisionを取得し、Wikiルール・出典・記事種別を決める。データ行の機械更新は既存の手順を使用し、文章推敲を挟まない。
2. 今回の**提案箇所のみ**「v1相当初稿」として書く。事実や引用は原典と照合し、既存のWiki形式で作る。これは旧版Skillを同時起動した結果ではない。
3. 対象ページに合わせて`page-profiles.md`の強度を決定。推敲が適さなければ初稿をそのまま採用する。
4. 本人紹介・企画記事などの地の文は`yomiyasu-adapter.md`で必要部分だけ一度推敲。本文中の称号・名言・世界観は`style-exceptions.md`に従い保持。
5. 利用可能なら次の保護手順を使用する。`python scripts/editorial_pipeline.py prepare --input proposal_v1.wiki --out editable.json`。出力の`editable`のみ編集可。`masked`に現れる`⟦MW...⟧`はそのまま残し、`edits`（segment_id→推敲後文字列）をJSONにする。`python scripts/editorial_pipeline.py apply --input proposal_v1.wiki --segments editable.json --edits edits.json --out proposal_v2.wiki`。記法保護・数字の増減で違反したら拒否する。**単一の提案部分**に対して使い、既存ページ全文を一括編集しない。
6. 診断は本文の保護済み地の文を対象にする。`deslop-ja`を必ずしも走らせる必要はない。指摘は候補であり、表現・固有の比喩・引用に該当すれば除外。`natural-japanese`から同梱した`paragraphs.py`は段落を分けるだけで判断はしない。追加固有情報検査`newfacts.py`には任意依存があり、`audit`は導入済みの場合のみ自動で起動し、未導入環境ではスキップして目視照合する。
7. `python scripts/editorial_pipeline.py audit --baseline proposal_v1.wiki --revised proposal_v2.wiki --json-out audit.json`。実行環境と読み出し権限があれば診断レポートを作り、トークン差分・数字・リンク・URL・タグ・候補語を確認。機械検査が通過しても、事実を無断追加していない保証にはならない。**AIが原文と根拠を必ず再読**する。重大な構文変更は採用しない。
8. 最新Wikiソースを基準に、既存§5の「追記」「置換」形式で最終的な差分案を作成。対象ページと反映位置を必ず明記。承認なしに公開しない。

## 通常モード／比較モード

- **通常（既定）**：Wiki変更差分だけを表示。初稿と完成稿の比較や内部評価点は出さない。文法・出典・記法に未解決の問題がある場合だけ報告。ローカルの`proposal_v1.wiki`などは必要な作業の間だけ利用し、不要なファイルをGitにコミットしない。
- **比較モード**：ユーザーが「比較」「A/Bテスト」「v1 v2」「推敲前後を見たい」と明示した場合にのみ、`audit`に`--compare-report comparison.md`を付ける。表示順は「①v1相当初稿（推敲前）→②v2推敲稿（後）→③変更点の差分→④採用理由／失敗・保護警告→⑤公開提案のWiki差分」。同じ根拠・初稿を用いた比較として扱う。検査結果は文章の主観的な自然さの点数ではない。
- v1 `.skill` とv2 `.skill` を互いに独立実行した比較をしたい場合は、明示的に両方を個別起動し**同一モデル・同一Wikiソース・同一資料**を用いる。そのとき上記のv1相当初稿との比較とは区別して表記する。

## ページ別ルーティングと例外

`page-profiles.md` と `style-exceptions.md` を参照。`[[...]]`、`{{...}}`、`<ref>`、引用、外部リンク、カテゴリ、ページ名、日付、数値、出典URL、表構造、見出しの意味を勝手に変えない。複雑なテンプレート・複数行の表やHTMLは機械処理から除外し、既存手順に従って差分確認する。

## 第三者診断器（同梱・オフライン）

```
python vendor/deslop-ja/check.py proposal_v2.wiki --json --reading-load
python vendor/natural-japanese/paragraphs.py proposal_v2.wiki --json
# 形態素解析が必要な精密Lint（任意）:
python vendor/natural-japanese/lint.py proposal_v2.wiki --json
# SudachiPy と sudachidict-core が任意で入っている環境に限定:
python vendor/natural-japanese/newfacts.py proposal_v1.wiki proposal_v2.wiki --json
```

**注意**：上記の診断器はMediaWiki記法を厳密に理解しない。判断に使う際は`prepare`が抽出した文章部分を入力にする方が適切。記法に反応した警告は除外してよい。全文へ自動修正をかけない。

## 受け入れ条件

詳しい品質ゲートと試験設計は `QUALITY-GATES.md` も読む。


- 不一致のある日付・数値・引用・リンク、ソース無しの事実追加、根拠のない推定心理、MediaWiki構文破損は**不採用**。
- `ご主人様`・しずくの主体性・意図した比喩・ユーモアの機械的な言い換えは**不採用**。
- 文章改善は、何が改善したかを具体的に説明できる時だけ採用。無理に書き換えない。
- 通常モードで比較情報を勝手に付けない。比較モードで旧版Skillが実行されたかのように表示しない。
