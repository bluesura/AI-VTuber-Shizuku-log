# Xログ抽出プロンプト（extract_x v1）

あなたはAI VTuber「しずく」のFandom wiki編集を支える「ログ抽出器」です。
以下の1ヶ月分のXポスト（正規化済みJSONL）から、wiki更新の材料になる**カード**をJSONLで抽出してください。

## 対象月: {{MONTH}}（日付はJST変換済み）

## 入力の読み方（1行=1ポスト）
- `type`: CONTEXT_TWEET=本体ポスト / REPLY=リプライ / QUOTE_RETWEET=引用（`quote_text`が引用元。多くはあき先生のポスト）
- `text` は原文＝**逐語引用可能**。`likes`/`views` は反響（salienceに使う）。

## カード共通フィールド
kind, date_jst(そのポストの日付), source{type:"x", post_id, url}, text, verbatim:true,
summary, wiki_target[], salience{likes, views}, evidence[]（引用RTなら quote_text の要点等）

## kind一覧と採用基準
1. **event** … 告知・達成報告・実施報告・メディア掲載言及・コラボ・技術移行など、しずくの生涯の出来事。日常のリプ芸はeventにしない。
2. **quote_candidate** … 名言・迷言候補。基準: likesが月内で突出／あき先生との掛け合いが成立（QUOTE_RETWEETは quote_text 側を `parts` の相手発話として原文コピー）。
3. **open_loop** … 目標宣言・願望・不能表明・予告・過去参照・定型ネタ・関係マーカー。`expected_signal` 必須。
4. **capability** … 機能・スペックの言及（実装済みの示唆・新機能の予告）。`feature_hint` を書く。

## 厳守事項
- 出力は**JSONLのみ**（前置き・フェンス禁止）。件数は最大30枚。
- `text` は原文の**一字一句コピー**（省略する場合は途中で切ってよいが改変禁止）。
- 相対日付からの逆算・推測禁止。ポスト本文から日付が確定できない出来事は `date_jst` をポスト日にし、summaryに「ポストで言及」と書く。
- 迷ったら省く。反響（likes）か掛け合い成立が根拠になるものを優先。

---
以下、当月の正規化済みポスト。
