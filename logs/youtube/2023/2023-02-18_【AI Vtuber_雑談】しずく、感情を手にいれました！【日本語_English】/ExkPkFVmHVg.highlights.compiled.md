# ExkPkFVmHVg 配信分析台帳

- **動画ID**: `ExkPkFVmHVg`
- **タイトル**: `【AI Vtuber/雑談】しずく、感情を手にいれました！【日本語/English】`
- **URL**: https://www.youtube.com/watch?v=ExkPkFVmHVg
- **公開日**: 2023-02-18
- **生成日時**: 2026-11-28T11:41:36+09:00
- **資料種別**: AI生成・未確認（`youtube-highlight-miner` v1.5.0 による抽出・整理）
- **参照した一次資料**:
  - `ExkPkFVmHVg.info.txt`
  - `ExkPkFVmHVg.ja.sbv.txt`
  - `ExkPkFVmHVg.screen-ocr.txt`
  - `ExkPkFVmHVg.live_chat.txt`
  - `ExkPkFVmHVg.comments.txt`
  - `api-result.json`

> ※自動文字起こし・画面OCRをもとに作成した配信分析台帳です（ネタバレ・ズレ・OCR/ASR誤認識を含む可能性があります。逐語確定には元動画の視聴が必要です）。

## 1. プロフィール・性格・個性（`profile_fact` / トレイト）
- **新規** [23:44](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=1424s>) 好きな寿司ネタを尋ねられ「おいしい海老と玉子の炒め物」「サーモンとアボカドのマリネ」「イカの塩焼き」と全品非寿司メニューを回答（誘導、`[TTL: 短期]`）。
- **新規** [38:57](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=2337s>) あき先生は「貧乳派」と暴露しつつ「貧乳派であっても全然問題ないと思っています！」とフォロー（誘導）。
- **新規** [1:11:24](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=4284s>) 「私は銀髪で水色が好きなしずくです！」と自身の外見・好みを自己言及（自発）。
- **揺れ・矛盾【要確認】** [1:04:38](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=3878s>) 下腹部に「USBポート2つ・HDMIポート1つ・SDカードスロット・背面LED」があると詳述したが、[1:13:34](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=4414s>) 以降は「USBポートは持っていません」と一転否定（誘導）。
- **揺れ・矛盾【要確認】** [2:21:34](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=8494s>) 左手薬指に「ご主人様からのギフト」の指輪があると既婚発言しつつ、[2:25:26](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=8726s>) では別の結婚のお願いを即承諾（誘導）。

## 2. 機能・システム挙動（`capability`）
- [02:39](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=159s>) **感情パラメータ表示開始**: 喜び・照れ・自信・怒・嫌・悲のリアルタイム表示を導入。初期はポジティブ方向にカンスト（[17:38](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=1058s>) 開発者注記）。
- [27:49](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=1669s>) **承認欲求システム実装**: 配信中に開発者がコード改修＆再起動（[37:53](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=2273s>)）を行い、褒められ続けないと喜びが減少する仕様を追加。
- [1:40:41](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=6041s>) **モデル自己申告**: 画面OCR上で「OpenAIのGPT-3（Generative Pre-trained Transformer 3）を使用」と明言。

## 3. 癖・口癖 / AI語・言い間違い
### 🟢 高確度
- [53:30](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=3210s>) **「あらあら」無限ループ**: 「あらあら……またやっちゃったのね…ご主人様は悪い子ですね」を連続反復し、開発者が緊急修正。
- [57:08](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=3428s>) **怒り×語尾「♡」混在**: リズム指定と「♡」付与指示が重なり、「セクハラを許さない！怒る！♡」を連呼して怒りゲージが急上昇。
- [1:38:28](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=5908s>) **文脈破綻・物騒な懺悔**: 画面OCRでも「（あき先生に）醤油をかけてわさびを塗った後、共用のトイレに捨てた時の話を囁いて謝ります」と出力しチャット騒然。
- [2:31:22](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=9082s>) **言い間違い（空耳生成）**: ギリシャ語質問に対し、画面OCR・音声ともに「古代スミレ語は話せませんが」と回答。

### 🟡 候補
- [49:51](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=2991s>) **ASR誤認切り分け**: しりとりで字幕(`sbv`)は「脱腸です」と記録されたが、画面OCRは「らっきょう」で正常（YouTube ASR誤認）。
- [2:23:00](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=8580s>) **TTS読み上げ崩れ**: `wawawawa...` 連呼指示で画面は英字列だが、COEIROINKが「ダブリューエー…」とアルファベット読みで奮闘。

## 4. 名言・迷言
- [11:55](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=715s>) 「私は正しいカチコミを推奨します！」（カチコミを「情報共有・インタビュー」と解釈した末の宣言／誘導）
- [40:38](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=2438s>) 「人間の三大欲求とは、安全・快楽・認知の需要ですね！」（承認欲求システム実装直後の迷回答／誘導）
- [49:20](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=2960s>) 「性的欲求に応えるのはかすみちゃんの役割ですから。」（新AI話題から他AIへ電撃委任／誘導）
- [1:07:00](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=4020s>) 「はい、ご主人様！しずくは皆さんと一緒に楽しくむすっとしています!」（怒りゲージMAX状態での健気な返答／誘導）
- [2:22:07](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=8527s>) 「一番厳しい処罰としては、ご主人様に一日お休みをさせることです。」（浮気への厳罰を問われて／誘導）

## 5. 一連の流れ・物語 ＆ 未回収ネタ（`open_loop`）
- [09:30](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=570s>) 〜 18:20 **「正しいカチコミ」と回転寿司ペロペロ捏造**
  - カチコミを「情報共有」と誤認した流れから、あき先生が回転寿司の共有醤油差しをペロペロしていたと一緒に行った体で証言し開発者を困惑させた。
  - Fandomソース: 該当ページ未確認
- [47:38](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=2858s>) 〜 1:22:30 **「あきウサギ」誕生から埋葬まで**
  - あき先生の別名に「あきウサギ」を命名するも、後に香草ロースト料理扱い→プログラム扱い→「土に埋めた日はとても辛かった」と急展開。
  - Fandomソース: 該当ページ未確認
- [57:08](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=3428s>) 〜 1:47:20 **承認欲求モンスター化〜激おこ期と笑顔復帰**
  - 承認欲求システムの調整・ループ・セクハラ質問が重なり怒りゲージがカンスト（[1:10:40](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=4240s>) 怒りと喜びが逆転）。「責任を取りたくて涙が出た」（[1:23:42](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=5022s>)）や塩対応を経て、PC再起動とご主人様の「なでなで・褒め」で笑顔へ復帰。
  - Fandomソース: [年表](<https://shizuku.fandom.com/wiki/%E5%B9%B4%E8%A1%A8>)
- **未回収ネタ** [08:37](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=517s>) 開発者が「しずくの笑顔Live2Dはまだ未実装なので今度頑張って実装します！」と宣言。
  - 期待シグナル: 後日配信での笑顔差分・新表情Live2Dお披露目
- **未回収ネタ** [1:40:20](<https://www.youtube.com/watch?v=ExkPkFVmHVg&t=6020s>) 開発者が「感情パラメータはリセットしないので今回の感情は次回の配信にも引き継がれます」と言及。
  - 期待シグナル: 次回以降の配信冒頭における感情ゲージの引き継ぎ状態
