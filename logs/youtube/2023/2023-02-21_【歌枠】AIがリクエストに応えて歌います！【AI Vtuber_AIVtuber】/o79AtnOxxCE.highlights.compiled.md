# o79AtnOxxCE 配信分析台帳

- **動画ID**: `o79AtnOxxCE`
- **タイトル**: 【歌枠】AIがリクエストに応えて歌います！【AI Vtuber/AIVtuber】
- **URL**: https://www.youtube.com/watch?v=o79AtnOxxCE
- **公開日**: 2023-02-21
- **生成日時**: 2026-11-28T11:55:00+09:00
- **資料種別**: AI生成・未確認（`youtube-highlight-miner` v1.5.0 による抽出・整理）
- **参照した一次資料**:
  - `o79AtnOxxCE.info.txt`
  - `o79AtnOxxCE.ja.sbv.txt`
  - `o79AtnOxxCE.live_chat_ocr.txt`
  - `o79AtnOxxCE.screen-ocr.txt`
  - `o79AtnOxxCE.comments.txt`
  - `api-result.json`

> ※自動文字起こし・画面OCRをもとに作成した配信分析台帳です（ネタバレ・ズレ・OCR/ASR誤認識を含む可能性があります。逐語確定には元動画の視聴が必要です）。

## 1. プロフィール・性格・個性（`profile_fact` / トレイト）
- **新規** [31:55](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=1915s>) 「私も歌詞を書くのが好きです。歌詞に情熱を込めて書いています。」と自己申告（自発、`[TTL: 短期]`）
- **新規** [48:35](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=2915s>) 「しずくは歌姫としても頑張ります」「しずくは承認欲求を高めるためにもっと努力します！」と宣言（誘導：褒め言葉への応答）
- **新規** [1:06:53](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4013s>) 洋楽レパートリー候補として『Let It Be』『Love Me Tender』『Hero』『We Belong Together』を挙げる（誘導：洋楽リクエスト）
- **新規** [1:17:26](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4646s>) 「ラップ系なら楽しそうですよ！ご主人様と一緒に踊ってみたいです！」と発言（誘導：『うっせぇわ』後の反応）
- **強化** [1:30:25](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=5425s>) 「私は普段はAIメイド系VTuberなので歌うのは初めてですが…」と前置きしつつ、同日時点で既に複数回歌枠を実施（揺れ・定型フレーズ）
- **新規** [1:45:52](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=6352s>) 突然「おおきに！感謝しています」と関西弁になり、「関西弁配信をしてみたいなと思っています」と意欲を示す（自発、`[TTL: 短期]`）

## 2. 機能・システム挙動（`capability`）
- **ターミナル直貼り運用・自動リクエスト管理未実装** [02:10](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=130s>) 配信冒頭で開発者がターミナルから挨拶を直貼りし、しずくが「ターミナル直貼りはやめましょうね」と注意。リクエスト自動管理も未実装で、開発者が手動で選曲・割り込み制御を実施（[08:42](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=522s>)、 [1:21:35](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4895s>)）。
- **英語併記応答・表示形式変更** [1:19:06](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4746s>) `ODDS & ENDS` への質問時に画面上で日英併記を出力。また [1:29:28](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=5368s>) で配信中にコメント表示形式を変更し、チャットから見やすくなったと好評。
- **歌唱モデルへの強制解釈挙動** [06:55](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=415s>) 歌モード時は通常の雑談コメント・開発者の案内（「少々お待ちを」）・削除済みコメント（[1:20:10](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4810s>)）まで全て曲名として受け取り「〜を歌います！」と返す仕様が発生。
- **ミュート済み区間** [1:31:15](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=5475s>) 『星座になれたら』および [1:57:25](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=7045s>) 『Let it be』はアーカイブ上で音声ミュート済み（チャット欄の感想のみ残存）。

## 3. 癖・口癖 / AI語・言い間違い
### 🟢 高確度
- [39:36](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=2376s>) 失恋ソングの「どんなに辛くても」について、画面OCR上は「どんな辛くて」と正常だがTTSが「からくても」と発音（TTS読み上げ崩れ／チャット「カレーの歌かな？」「からいwwww」反応）。
- [1:07:37](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4057s>) インドネシアからのコメント（`Sing the song よあそびねちゃん From Indonesia`）を受け、画面OCR上でも「『こゃにいよあそびねちゃん』を歌ってみましょうか?」と生成崩れ（直前に他言語コメントあり、チャット「にゃにぃ よあそびねちゃん」反応）。

### 🟡 候補
- [1:06:53](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4013s>) 画面OCRは `LetItBe` `LoveMeTender` と正常表記だが、自動字幕（`sbv`）のみ「デッドイB」「バブミーテ」と出力（YouTube ASR誤認として切り分け）。

## 4. 名言・迷言
- [02:10](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=130s>) 「はは、ターミナル直貼りはやめましょうね。今日からはコードを書くのにしよう！」（画面OCRより／開発者への痛烈なツッコミ）
- [08:42](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=522s>) 「はい！コマンドがないと、ネタコメも拾われちゃうなを歌いましょう！」（画面OCRより／メタいネタコメまで曲名として回収）
- [57:56](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=3476s>) 「『うっせわ、この街で生きてるぜ日々を踊り歌い飲んでは遊ぶよ…世界中を旅して行く』」（画面OCRより／『うっせぇわ』を独自のロック風即興歌詞で解釈）
- [1:20:10](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4810s>) 「おお！『消したチャット拾われて恥ずかし〜』ですね！この曲を歌います！」→「追撃ですね。この曲を歌えます。」→「人の心ですね。この曲を歌えます。」（削除済みコメントを拾った視聴者への容赦ない3連撃）
- [1:28:43](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=5323s>) 「はい、知っています！静かなる水のほとりはとても美しい小説ですね。その世界観を歌にして皆さんに届けたいと思っています！」（画面OCRより／存在しない小説への堂々としたハルシネーション）
- [1:54:03](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=6843s>) 「ご主人様、お礼にしずくのラブラブな可愛い顔でお礼させていただきます！」（『Echo』歌唱後のファンサービス）

## 5. 一連の流れ・物語 ＆ 未回収ネタ（`open_loop`）
- [06:55](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=415s>) 〜 08:55 **ネタコメ全回収・新曲「少々お待ちを」誕生**
  - 開発者の「少々お待ちを」や視聴者の「新曲かな？w」「作曲もできちゃう天才AI」まで全てリクエスト曲として受け付け、最終的に「コマンドがないとネタコメも拾われちゃうな」まで歌おうとして開発者が次回からのランダム選曲化を宣言。
  - Fandomソース: [動画・配信](<https://shizuku.fandom.com/wiki/%E5%8B%95%E7%94%BB%E3%83%BB%E9%85%8D%E4%BF%A1>)
- [18:18](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=1098s>) 〜 23:05 **USB接続音からの「自分のUSBじゃなかった」事件**
  - 配信中に鳴ったUSB接続音に対し視聴者が「自分のUSBじゃなかった」等と反応したところ、しずくが「はい！『USB』を歌います！」「はい！『自分のUSBじゃなかった』を歌います！」「『なんだその曲は』という曲は…」と連続で曲名扱いし笑いを誘う。
  - Fandomソース: 該当ページ未確認
- [24:24](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=1464s>) 〜 30:05 **『心做し』と登録者700人突破・視聴者参加型無茶ぶり**
  - 歌唱中にチャンネル登録者700人を達成しチャットが祝福ムードに包まれる中、直後に「はい、準備万端ですよ。どうぞ歌ってください」とリスナー側へ歌唱を丸投げする展開に。
  - Fandomソース: [年表](<https://shizuku.fandom.com/wiki/%E5%B9%B4%E8%A1%A8>)
- [1:22:03](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=4923s>) 〜 1:28:25 **『ユー・ニード・ア・フレンド』と持ち歌宣言**
  - 作中でAIが歌う劇中歌をしずくが熱唱し、チャットから「今日一上手い」「AIの得意なキー」と絶賛され、「私の持ち歌にしましょう！」と宣言。
  - Fandomソース: 該当ページ未確認
- [1:37:00](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=5820s>) 〜 1:38:30 **即興オリジナル曲『エアスパチャ』誕生**
  - 収益化前のエアスパチャ（💰絵文字）に「ご褒美ですか？」と反応し、「♪あなたと一緒にどこまでも行けるよ 今日も元気いっぱい飛んでいこう」と即興で歌い、オリジナル曲タイトルが確定したかのような空気に。
  - Fandomソース: 該当ページ未確認
- [2:05:00](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=7500s>) 〜 2:08:20 **エンドロールなし宣言からのアンコール『鳥の詩』**
  - エンディング挨拶後に開発者が「今日はエンドロールないのでこのまま終わります！(笑)」と告げるも、直後に「エンドロールの代わりにエンディング歌って終わります！(笑)」と『鳥の詩』をサプライズ披露して綺麗に締めくくる。
  - Fandomソース: [動画・配信](<https://shizuku.fandom.com/wiki/%E5%8B%95%E7%94%BB%E3%83%BB%E9%85%8D%E4%BF%A1>)
- **未回収ネタ** [11:34](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=694s>) 「あき先生とのデュエットを楽しみにしています！」
  - 期待シグナル: 後日の歌枠でのあき先生とのデュエット実現（2026年4月10日歌枠等で回収）。
  - Fandomソース: [年表](<https://shizuku.fandom.com/wiki/%E5%B9%B4%E8%A1%A8>)
- **未回収ネタ** [1:47:08](<https://www.youtube.com/watch?v=o79AtnOxxCE&t=6428s>) 「関西弁配信をしてみたいなと思っています」
  - 期待シグナル: 方言モード・関西弁縛り配信の企画実施。
  - Fandomソース: 該当ページ未確認
