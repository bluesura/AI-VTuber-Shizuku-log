# Wiki向け yomiyasu 3.1.0 アダプター

添付のyomiyasu 3.1.0は `../../vendor/yomiyasu/` に同梱する。Wiki用の対象選定・形式・出力はこのアダプターに従い、文章の推敲には同梱の `SKILL.md` §1と必要な参照資料（特に `references/rephrase-test.md`）を用いる。Wikiの編集規則、対象ページの声と語彙、MediaWiki記法を優先する。

## 推敲する範囲

- 出典で確認済みの追加・置換部分の地の文で、読者が意味を取りにくい箇所を選ぶ。本人の呼称・意図した比喩・ユーモア、引用、数値、固有名詞、時系列、出典、見出し、箇条書きの形式を維持する。
- 言い直す前後で、対象、肯定・否定、行為者、条件と範囲、断定・推量・伝聞の強さ、数値・固有名詞・時期を照らし合わせる。変化があれば元へ戻して根拠を再確認する。出典を補う必要があるときはWikiの調査工程へ戻す。
- 年表は先に `page-timeline.md` §2-1・§4で視点を決める。初稿の視点修正は出典に基づく編集として扱い、局所推敲と分ける。文末は年表の書式に従う。読みやすい行を含む全項目の意味的レビューは別途 `page-timeline.md` §7で行う。

## 同梱CLIで検査する

1. 推敲する地の文を同じ範囲・行順で原稿と最終稿に分け、UTF-8の作業ファイル（例 `prose_before.txt` と `prose_final.txt`）に置く。双方から引用と保護対象のWiki記法を外して照合用に抜き出す。分離すると文意が変わる箇所は目視で照合する。
2. 原稿に `yomiyasu_lint.py` をかけ、候補を前後の文と続けて読む。同梱版の言い直しテストで採否を決め、推敲後の文を `prose_final.txt` に保存する。
3. `run` で検査し、残った候補を確認する。最終稿を直したときは再度 `run` を実行する。Wikiへ戻す直前に同じ最終稿で `verify` を実行する。Wiki記法を復元した本文は `editorial_pipeline.py` と目視で別に検査する。

```text
python -X utf8 vendor/yomiyasu/scripts/yomiyasu_lint.py prose_before.txt --no-words
python -X utf8 vendor/yomiyasu/scripts/yomiyasu_check.py run --source prose_before.txt --final prose_final.txt --fact-gaps --no-words --state-dir review-state
python -X utf8 vendor/yomiyasu/scripts/yomiyasu_check.py verify --source prose_before.txt --final prose_final.txt --state-dir review-state
```

作業ディレクトリは原稿を含む場所とし、CLIのパスを展開先に合わせる。状態ディレクトリは作業ごとに分け、原稿・記録とともにGit管理外へ置く。CLIの実行と照合結果を記録し、利用できない場合は未実施と理由を残して目視照合する。候補件数で文の良し悪しを決めない。ユーザー向けの出力はWiki差分の書式を使う。
