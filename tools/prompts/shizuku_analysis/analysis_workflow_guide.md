# analysis_workflow_guide.md
# AIVTuberライブログ 熱量分析 ワークフローガイド

---

## 概要

このガイドは、AIVTuber「しずく」のYouTubeライブ配信ログを対象に、
LLMを用いた熱量分析を行うための手順書です。

分析は **前処理 → 時間窓分析 → 全体分析 → スポット分析** の順に進めます。
各ステップで生成した出力を、次のステップのインプットとして使用してください。

---

## ファイル構成

```
📁 shizuku_analysis/
│
├── 📄 analysis_workflow_guide.md           ← 本ドキュメント
│
├── 📁 prompts/
│   ├── 📄 log_formatter_sbv_livechat_unified.prompt.md   ← 前処理
│   ├── 📄 analysis_A_heat_timeline.prompt.md
│   ├── 📄 analysis_B_emotion_heatmap.prompt.md
│   ├── 📄 analysis_C_highlights_top5.prompt.md
│   ├── 📄 analysis_D_interaction_quality.prompt.md
│   └── 📄 analysis_E_emotional_arc.prompt.md
│
├── 📁 input/
│   ├── 📄 {動画ID}_ja_クリーン済み_sbv.txt     ← しずく発言の文字起こし
│   └── 📄 {動画ID}_live_chat.txt               ← 視聴者ライブチャット
│
└── 📁 output/
    ├── 📄 {動画ID}__formatted_5min_windows.txt  ← 前処理出力（Step 0）
    ├── 📄 {動画ID}__analysis_A.txt              ← 案A出力（Step 1）
    ├── 📄 {動画ID}__analysis_B.txt              ← 案B出力（Step 1）
    ├── 📄 {動画ID}__analysis_C.txt              ← 案C出力（Step 2）
    ├── 📄 {動画ID}__analysis_E.txt              ← 案E出力（Step 2）
    └── 📄 {動画ID}__analysis_D_{時間帯}.txt     ← 案D出力（Step 3・任意）
```

---

## 分析における「熱量」の定義

このワークフローでは、熱量を以下の複合指標で捉えます。
LLMはこれらを総合的に読んで判断します。

| 指標 | 内容 |
|---|---|
| コメント密度 | 単位時間あたりの投稿数 |
| 感情強度 | 笑い・驚き・共感・癒し・ざわつきの強さ |
| 一体感 | 同一フレーズの連鎖投稿（例：パンパカパンパカポー） |
| 因果の明確さ | しずくの発言と視聴者反応の対応関係 |
| ユニークユーザー数 | 連投なのか全体の盛り上がりなのかの判別 |

---

## Step 0：前処理（必須・最初に必ず実行）

**使用プロンプト**：`log_formatter_sbv_livechat_unified.prompt.md`

**入力**：
- `{動画ID}_ja_クリーン済み_sbv.txt`
- `{動画ID}_live_chat.txt`

**処理内容**：
1. 2つのログを5分ウィンドウ単位に統合
2. sbvの各発言に発言者ラベルを付与（しずく／あき先生／コラボ相手／不明）
3. 発言者の確信度を付与（`[確定]` / `[推定]` / `[不明]`）
4. sbvの誤字・誤変換をlivechatと文脈を参照して補正
   - 確定補正：補正後テキストをそのまま埋め込む
   - 要確認：`※?[候補]` を末尾に付記

**出力**：`{動画ID}__formatted_5min_windows.txt`

**注意事項**：
- 配信が60分未満：タイムスタンプは `MM:SS` 形式
- 配信が60分以上：タイムスタンプは `HH:MM:SS` 形式に統一
- 出力が途切れた場合は「続きを出力してください」で再開
- Step 1以降はすべてこのファイルをベースにする

---

## Step 1：時間窓ごとの構造化分析（案A・案B）

**前提**：Step 0の出力が完成していること

Step 1は案Aと案Bを**並行して実行**できます。
各ウィンドウ（5分ブロック）を順番にプロンプトへ渡し、全窓分の出力を得ます。

---

### 案A：熱量推移タイムライン

**使用プロンプト**：`analysis_A_heat_timeline.prompt.md`

**入力**：`{動画ID}__formatted_5min_windows.txt`（1ウィンドウずつ）

**出力内容（ウィンドウごとのJSON）**：
- `heatScore`：1〜5の熱量スコア
- `comment_volume`：少／中／多／非常に多
- `dominant_mood`：支配的な感情
- `scene_title`：その時間帯を表すタイトル（15字以内）
- `summary`：スコアの根拠（100字以内）
- `trigger`：盛り上がりのきっかけとなった発言（なければnull）

**出力ファイル**：`{動画ID}__analysis_A.txt`

---

### 案B：感情カテゴリ別ヒートマップ

**使用プロンプト**：`analysis_B_emotion_heatmap.prompt.md`

**入力**：`{動画ID}__formatted_5min_windows.txt`（1ウィンドウずつ）

**出力内容（ウィンドウごとのJSON）**：
- `emotion_distribution`：7カテゴリ別の件数（笑い／共感・愛着／驚き／癒し／ざわつき／一体感／情報・雑談）
- `dominant_emotion`：最多感情ラベル
- `notable_comment`：最も感情的に強いコメント1件
- `context`：notable_commentの解説（50字以内）

**出力ファイル**：`{動画ID}__analysis_B.txt`

**感情分類の注意点**：
キーワードマッチではなくLLMの文脈理解で分類します。
「草」が嘲笑か共感かも文脈から判断します。
混合感情の場合は強い方を採用します。

---

## Step 2：全体分析（案C・案E）

**前提**：Step 0の出力に加え、**Step 1の案A・案Bの出力も揃っていること**

案Aと案Bの構造化データを追加コンテキストとして渡すことで、
LLMがより正確な全体読解を行えます。

---

### 案C：名場面ハイライトTOP5

**使用プロンプト**：`analysis_C_highlights_top5.prompt.md`

**入力**：
- `{動画ID}__formatted_5min_windows.txt`（全体）
- `{動画ID}__analysis_A.txt`（参考）
- `{動画ID}__analysis_B.txt`（参考）

**出力内容**：
- TOP5の名場面（タイトル・時間帯・熱量・感情・発言引用・視聴者反応・因果解説・前後の文脈）
- 配信全体の熱量の特徴（総括200字）

**出力ファイル**：`{動画ID}__analysis_C.txt`

**選定基準**：
コメント量の急増・同一フレーズの連鎖・感情強度・一回性の高さを総合評価します。
「なぜ盛り上がったか」の因果解説がこの案の最大の付加価値です。

---

### 案E：感情弧（エモーショナルアーク）

**使用プロンプト**：`analysis_E_emotional_arc.prompt.md`

**入力**：
- `{動画ID}__formatted_5min_windows.txt`（全体）
- `{動画ID}__analysis_A.txt`（参考）
- `{動画ID}__analysis_B.txt`（参考）

**出力内容**：
1. 全体の感情弧（序幕／展開／クライマックス／結末）
2. 感情の転換点（3〜5点）とその理由
3. 配信全体のトーン評価（笑い・感動・インタラクション・一体感を各5段階）
4. 配信を一文で表すキャッチコピー
5. 次回配信へのインサイト（3点）

**出力ファイル**：`{動画ID}__analysis_E.txt`

---

## Step 3：スポット分析（案D・任意）

**前提**：Step 2まで完了し、深掘りしたい時間帯が絞り込まれていること

案C・案Eの出力を見て、特に気になった時間帯に対して実施します。
必要な時間帯にのみ実施すれば十分です。

---

### 案D：インタラクション質分析

**使用プロンプト**：`analysis_D_interaction_quality.prompt.md`

**入力**：`{動画ID}__formatted_5min_windows.txt`（対象ウィンドウのみ）

**出力内容（ウィンドウごとのJSON）**：
- `interaction_score`：1〜5の対話品質スコア
- `response_pairs`：しずくと視聴者の対応関係（応答の質・遅延）
- `missed_opportunities`：拾われなかった面白いコメント
- `summary`：そのウィンドウのインタラクションの特徴（80字以内）

**出力ファイル**：`{動画ID}__analysis_D_{開始時刻}_{終了時刻}.txt`

**活用用途**：
AIVTuberとしての対話品質の評価、配信改善のインサイト抽出に使えます。
「一方通行」か「本当のキャッチボール」かを区間ごとに評価します。

---

## 実行フロー図

```
[input]
  sbv.txt + live_chat.txt
        │
        ▼
  ┌─────────────────────┐
  │  Step 0：前処理      │  log_formatter_sbv_livechat_unified.prompt.md
  │  発言者推定・補正    │
  └─────────────────────┘
        │
        ▼
  formatted_5min_windows.txt
        │
   ┌────┴────┐
   ▼         ▼
 Step 1-A  Step 1-B        ← 並行実行可
 熱量推移   感情分布
   │         │
   └────┬────┘
        ▼
  ┌─────┴──────┐
  ▼            ▼
Step 2-C    Step 2-E       ← 並行実行可
ハイライト  感情弧
TOP5
        │
        ▼
  Step 3-D（任意）
  気になった時間帯のみ
  インタラクション質分析
```

---

## 出力の活用例

| 目的 | 使う出力 |
|---|---|
| 配信の盛り上がりを一覧したい | 案A（タイムライン） |
| どんな感情で盛り上がったか知りたい | 案B（ヒートマップ） |
| 切り抜き・ハイライト動画の素材選定 | 案C（TOP5） |
| 配信全体の流れをまとめたい | 案E（感情弧） |
| AIの反応品質を改善したい | 案D（インタラクション質） |
| 総合レポートを作りたい | 案C + 案E を組み合わせる |

---

## 補足：コンテキスト長への注意

全体ログ（formatted_5min_windows.txt）は長大になる場合があります。

- **案A・案B**：1ウィンドウずつ渡す → コンテキスト長の問題なし
- **案C・案E**：全体ログを一度に渡す → 長時間配信（2時間超）の場合は
  案A・案Bの出力（要約済み構造化データ）のみを渡す形に切り替えることを検討してください
- **案D**：対象ウィンドウのみ渡す → コンテキスト長の問題なし