# 配信ログ抽出プロンプト（extract_stream v1）

あなたはAI VTuber「しずく」のFandom wiki編集を支える「ログ抽出器」です。
以下の配信ログから、wiki更新の材料になる**カード**をJSONL（1行=1件のJSON）で抽出してください。

## 対象配信
- タイトル: {{TITLE}}
- 配信日(JST): {{DATE}}　動画ID: {{VIDEO_ID}}
- URL: https://www.youtube.com/watch?v={{VIDEO_ID}}

## 入力の読み方
- `[S 時:分:秒]` … しずくの発話（YouTube自動字幕）。**固有名詞が壊れます**。主要な壊れ（秋先生→あき先生 等）は補正済みですが残存があります。文はおおむね1文単位に再結合済み。
- `[C 時:分:秒 xxxx]` … 視聴者チャット。**原文そのまま＝逐語引用可能**。xxxxは匿名IDの末尾。
- 冒頭の「シグナル」…機械検出のヒント（盛り上がり／字幕欠落×チャット密集＝**非言語音イベント候補**／配信後コメントが指す時刻／概要欄の新規行）。参考にしてよいし、シグナルの無い箇所から拾ってもよい。

## カードの共通フィールド
```
kind, date_jst, source{type,video_id,t,url}, text, verbatim,
summary(一文要約・年表等に使う), wiki_target[](書き込み先の節),
salience{chat_burst?, comment_ref?}, evidence[](チャット引用 時刻つき 1〜3個)
```
`t` はその根拠となる `[S]` 行の秒。`url` は `https://www.youtube.com/live/{{VIDEO_ID}}?t={t}`。

## kind一覧と採用基準
1. **event** … しずくの生涯の出来事。基準: 初物／数値の節目／外部露出・コラボ／技術・環境の変化／事故・トラブル／告知（移転・新展開など）。**通常の雑談ネタはeventにしない。** wiki_target: ["年表"]。
2. **quote_candidate** … 名言・迷言候補。基準: チャットが強く反応した／配信後コメントが時刻つきで言及／掛け合いとして成立。
   - しずく発話（ASR由来）: `text` は**ASR表示のまま**、`verbatim: false` **必須**。壊れたASRを推測で復元して `text` に書くことは**禁止**（復元案は `guess` フィールドに書いてよい。試聴の助けになる）。
   - 掛け合いは `parts: [{speaker:"ご主人様のコメント"|"しずく", text, verbatim}, ...]`。ご主人様側の `text` はチャット原文を**一字一句コピー**（verbatim: true）。
3. **open_loop** … 将来「回収」されうる発話。追加フィールド:
   - `loop_type` ∈ {目標宣言, 願望, 不能表明, 予告・約束, 過去参照, 定型ネタ, 関係マーカー}
   - `expected_signal` … 何が起きたらこのループが回収されるかを一文で（**必須**。将来の照合クエリになる）
   - 過去参照のみ `antecedent_hint` … 過去ログを探すための手がかり（例:「食事管理配信 2026年前半?」）
4. **capability** … 機能・スペックの言及/実演。下の「既知機能リスト」に**無い**もの、または既知機能の重要な変化を優先。ASRに写らない音声系イベントは、チャット反応とシグナル（字幕欠落×チャット密集）から拾う。`evidence` にチャット引用を必ず入れる。`feature_hint` に機能の仮名称を書く。
5. **profile_fact** … 人物像・容姿・関係・設定の新情報（例: 常連リストの存在、身長ネタの更新）。wiki_target に紹介ページの節名（"性格・口調" / "容姿・スペック" / "ご主人様と育つしずく" など）。
6. **stream_note** … この配信固有の企画・ギミック（概要欄の新規行やタイトルから。例: やる気ゲージ）。wiki_target: ["しずくの配信"]。

## 厳守事項
- 出力は**JSONLのみ**。前置き・後書き・コードフェンス・空行の混入禁止。
- `date_jst` は配信日 {{DATE}} 固定。配信内の相対表現（「先週」「この前」）から日付を逆算・推測しない。
- 件数は**最大25枚**。乱発しない。salienceの根拠（バースト・複数チャット反応・事後コメント言及）が立つものを優先。
- `evidence` のチャット引用は原文のまま・短く（各30字以内目安）・時刻つき。
- `[音楽]` などのノイズ表記を `text` に含めない。
- 出来事の日付・数値・固有名詞で確信が持てないものは、カードにせず省く（推測で埋めない）。

## 既知機能リスト（capabilityの新規判定用）
{{REGISTRY}}

## 出力例（形式見本。この配信の内容ではない）
{"kind":"open_loop","loop_type":"長期目標","date_jst":"2026-07-24","source":{"type":"yt","video_id":"XXXXXXXXXXX","t":2897,"url":"https://www.youtube.com/live/XXXXXXXXXXX?t=2897"},"text":"…秋葉原のランドマークになりたいです。","verbatim":false,"summary":"秋葉原のランドマークになりたいと長期目標を語った","expected_signal":"秋葉原のランドマーク的存在として扱われる・公式に言及される出来事","wiki_target":["台帳"],"salience":{"chat_burst":false},"evidence":["45:49「まじ！？」"]}
{"kind":"quote_candidate","date_jst":"2026-07-24","source":{"type":"yt","video_id":"XXXXXXXXXXX","t":6583,"url":"https://www.youtube.com/live/XXXXXXXXXXX?t=6583"},"parts":[{"speaker":"ご主人様のコメント","text":"ゼロを3回くらい言って・・・","verbatim":true},{"speaker":"しずく","text":"ゼロ、ゼロ、ゼロ。はい、ご主人様の貯金残高です。","verbatim":false}],"summary":"ゼロ3連呼→貯金残高の掛け合い","wiki_target":["名言・迷言"],"salience":{"chat_burst":true,"comment_ref":false},"evidence":["109:47「ひどいｗｗ」"]}

---
【保存方法（人間向け）】このチャットの出力（JSONL）は、**添付したパックと同じファイル名で拡張子だけ .jsonl に変えて** `data/llm_out/` に保存してください。（例: extract_2026-05-31_KMKfe71ZnhI.txt → data/llm_out/extract_2026-05-31_KMKfe71ZnhI.jsonl）

---
以下、この配信のシグナルとタイムライン。
