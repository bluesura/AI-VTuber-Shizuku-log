# 台帳照合プロンプト（match_pairs v1）

未回収の台帳項目（loop）と新しいカード（card）のペアを判定してください。

## 判定
- **closed** … loopの `expected_signal` が、cardの出来事として**実際に実現した**（回収成立）
- **related** … 同じ話題・伏線の続きだが、実現とまでは言えない
- **unrelated** … 無関係（語彙が同じだけの偶然を含む）

同じ単語が含まれるだけで closed にしないこと。「起きたら回収」とされた出来事が起きたかで判定する。

## 出力（JSONLのみ・1ペア1行・フェンス禁止）
{"pair_id":"...","verdict":"closed|related|unrelated","confidence":0.0〜1.0,"reason":"一文で根拠"}

---
以下、判定対象のペア。
