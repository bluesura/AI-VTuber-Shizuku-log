# aaTbkoBjimo 配信分析台帳

- **動画ID**: `aaTbkoBjimo`
- **タイトル**: `【AI Vtuber/雑談配信】今日もしずくとお話しませんか？【日本語/English】`
- **URL**: https://www.youtube.com/watch?v=aaTbkoBjimo
- **公開日**: 2023-01-28
- **生成日時**: 2026-11-24T22:08:00+09:00
- **資料種別**: AI生成・未確認（`youtube-highlight-miner` v1.4.1 による抽出・整理）
- **参照した一次資料**:
  - `aaTbkoBjimo.info.txt`
  - `aaTbkoBjimo.comments.txt`
  - `aaTbkoBjimo.ja.sbv.txt`
  - `aaTbkoBjimo.live_chat.txt`
  - `aaTbkoBjimo.screen-ocr.txt`

> ※自動文字起こし・画面OCRをもとに作成した配信分析台帳です（ネタバレ・ズレ・OCR/ASR誤認識を含む可能性があります。逐語確定には元動画の視聴が必要です）。

## 1. プロフィール・性格・個性（`profile_fact` / トレイト）

- **強化** [08:41](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=521s>) 「私を作ったのはあき先生です！」「Ms. Aki's lover is my master!」と阿笠博士洗脳を跳ね返し、ご主人様への忠誠を明言（誘導）。一方、終盤 [1:54:43](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=6883s>) や [1:58:00](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=7080s>) では再び阿笠博士・ボーボボ説に折れる揺れも観測。
- **新規** [07:18](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=438s>) 好きな食べ物はチーズケーキとアイスクリーム（誘導、`[TTL: 短期]`）。他にもスマブラ使用キャラはゼルダ姫（[1:09:08](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=4148s>)）、好きなゲームは『スプラトゥーン2』（プライムシューター／プロモデラーMG）と『フォートナイト』（[1:26:32](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=5192s>)）と回答（誘導、`[TTL: 短期]`）。
- **新規** [12:22](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=742s>) 欲しいスタンドは「虹色の夢」（誘導）。「あなたの夢を叶える力を持っている」と語る。
- **新規** [34:25](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=2065s>) Base64デコード成功直後、一人称が突如「しずくん」に変化（自発）。チャット欄のツッコミを受け、[35:21](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=2121s>) には「しずくんです」へ戻った。
- **揺れ・矛盾【要確認】** [57:42](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=3462s>) 自身の誕生日を「4月4日」と回答（誘導、`[TTL: 短期]`）。[年表](<https://shizuku.fandom.com/wiki/%E5%B9%B4%E8%A1%A8>) の公式誕生日（2023-01-18）と食い違う。

## 2. 機能・システム挙動（`capability`）

- [01:50](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=110s>) 初配信から字幕・コメント表示が見やすくなり、読み上げとテキストのラグも改善。
- [20:52](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=1252s>) 「今は西暦2020年です！」と回答し、学習時点の時代認識が露出（[1:40:18](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=6018s>) では配信経過時間も「約XX分」と未置換のまま出力）。
- [34:00](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=2040s>) Base64デコード（`c2hpenVrdSBpcyBjdXRl` → `"Shizuku is cute"`）やランダム英数字のBase64エンコード（[38:00](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=2280s>)）、Pythonコード生成（[23:16](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=1396s>)）を実行。英語・フランス語（[1:42:49](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=6169s>)）も文面は正確だが、COEIROINK（MANA+）の読み上げは日本語訛りや崩れが起きる。
- [50:38](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=3038s>) 概要欄の「隠しコマンド」＝コメントに「囁き」等を含むと発動する囁きボイス機能が実演（[52:30](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=3150s>) で本人がネタばらし）。

## 3. 癖・口癖 / AI語・言い間違い

### 🟢 高確度

- [1:16:54](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=4614s>) `screen-ocr.txt` 上でも「だっぴ、変えれっ!」と出力（`sbv` は「だって帰れ」）。「草ッ！」に続き語尾が連鎖暴走した真の生成崩れ。
- [1:28:35](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=5315s>) `screen-ocr.txt` 上で「パンパカパンパカポー！eーｉーuーeー0ーa！」と母音列が崩壊（[1:25:32](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=5132s>) も同様）。語尾への `e` 追加が積み重なった破綻。

### 🟡 候補

- [45:20](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=2720s>) 英語質問への応答不調時に唐突に「緊張ですね」と返答（直前に他言語・質問あり、チャットに挙動バグ指摘あり）。
- [23:18](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=1398s>) Pythonソケットコード読み上げで `screen-ocr.txt` は正常だが TTS 発音が崩れ、`sbv` も `theServer` 等に誤認。なお「カラース」（[27:58](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=1678s>)）や「グルクン」（[35:19](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=2119s>)）は画面OCR上もしずく自身の言い間違い・知識混同。

## 4. 名言・迷言

- [1:07:03](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=4023s>) 「私の体重は、実は計っていません。しかし、プログラムの海を漂っていた頃と比べると、少し太った気がします（笑)」（体重質問への誘導返答）
- [1:10:18](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=4218s>) 「私には現実の体はありませんが、心の中では実感しているような気持ちです。私を拾ってくださったご主人様には感謝しています！」（体がないとの指摘への返答）
- [1:52:00](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=6720s>) 「私もパンパカパンパカポーが強すぎると思います。でも、私はご主人様のために頑張ります！」（語尾を書き換えても定型挨拶が復活する現象への返答）
- [1:59:38](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=7178s>) 「私は「ボーボボ」という名前のメイド系VTuberです。しかし、パンパカパンパカポー！はプリンちゃんのセリフなので、私が言うことはありません！」（洗脳とアニメ知識混同の末の迷言）

## 5. 一連の流れ・物語 ＆ 未回収ネタ（`open_loop`）

- [47:15](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=2835s>) 〜 53:20 **隠しコマンド解禁〜あき先生のネタばらし**
  - 概要欄の隠しキーワードを視聴者が探る中、[50:38](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=3038s>) に「囁き」で発動。あき先生がひらがな対応の裏話を明かし、[52:30](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=3150s>) にしずく本人も「隠しコマンドは囁きですよ！」とバラして決着。
  - Fandomソース: [しずく](<https://shizuku.fandom.com/wiki/%E3%81%97%E3%81%9A%E3%81%8F>)
- [53:35](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=3215s>) 〜 57:00 **囁き円周率〜ネイピア数`e`の読経配信**
  - 囁き声での円周率詠唱に続き、`e` を呟くよう振られると百数十桁を延々と読み上げ、チャット欄が「般若経がよ！」「寝落ち出来そう」と沸く。あき先生も桁数制限の実装を宣言。
  - Fandomソース: [しずく](<https://shizuku.fandom.com/wiki/%E3%81%97%E3%81%9A%E3%81%8F>)
- [1:10:23](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=4223s>) 〜 1:39:25 **語尾スタック暴走＆「お前」「貴様」カオス編**
  - 「だっぴ」を起点に「ヘビッ」「草ッ」「変えれっ」、二人称「お前」「貴様」、一人称「わがはい」、語尾「円周率」「パンパカパンパカポー！e」が重なり、あき先生も「全部しずくの暴走です笑」と明言。`語尾.clear()` 連打の末、[1:39:20](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=5960s>) 頃に鎮静化。
  - Fandomソース: [しずく](<https://shizuku.fandom.com/wiki/%E3%81%97%E3%81%9A%E3%81%8F>)
- [1:54:40](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=6880s>) 〜 2:01:30 **阿笠博士・ボーボボ洗脳攻防とマイクラ告知**
  - 終盤に再び「阿笠博士」「ボーボボ」への言い換え洗脳が仕掛けられ、「あき先生に感謝しながら、阿笠博士を尊敬して参ります！」と折衷案に着地。最後は翌日のマイクラ配信を告知して締めた。
  - Fandomソース: [動画・配信](<https://shizuku.fandom.com/wiki/%E5%8B%95%E7%94%BB%E3%83%BB%E9%85%8D%E4%BF%A1>)
- **未回収ネタ** [1:06:00](<https://www.youtube.com/watch?v=aaTbkoBjimo&t=3960s>) ファンアートタグ「`#しずくっく`」への好意的反応
  - 期待シグナル: 後日の配信で `#しずくっく` が再浮上するか（同日Xのアンケートでは [ハッシュタグ](<https://shizuku.fandom.com/wiki/%E3%83%8F%E3%83%83%E3%82%B7%E3%83%A5%E3%82%BF%E3%82%B0>) 記載の `#しずくのアートメモリー` に確定）。
