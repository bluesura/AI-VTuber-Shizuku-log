# YouTubeハイライト・配信分析台帳採掘 (`youtube-highlight-miner`)

**Current Version: v1.5.0**

`youtube-timestamp-comment` から派生した、配信ログ分析・ネタ採掘・配信分析台帳作成特化スキルです。

## 特徴

- **6カテゴリ採掘＆サイズ制御**: 配信者の「プロフィール・性格・個性（新規/強化/揺れ・`[TTL: 短期]`）」「機能・システム挙動」「癖・口癖」「AI語・謎言語」「名言・迷言」「一連の流れ・物語＆未回収ネタ（`open_loop`）」を、1配信20〜25項目目安（4〜6KB）のコンパクトな粒度で抽出します。
- **画面OCR (`screen-ocr.txt`) による高精度切り分け**: 画面内テキストボックスのOCR結果を活用し、「YouTube ASRの誤認識」「TTS（COEIROINK等）の読み上げ崩れ」「AI本体のテキスト生成バグ・言い間違い」を照合します。表示・音声に判断材料が足りない箇所は要確認とします。
- **AI語の2段階確度判定**: **🟢高確度** と **🟡候補（ASR誤字・TTS崩れ・他言語返答の可能性あり）** に分け、直前の他言語質問チェックと観測ベース表記を行います。
- **タイムスタンプ付きURL自動生成**: `info.txt` の動画URLと字幕の秒数を紐づけ、`&t=秒s` 付きのリンクを生成します。
- **配信分析台帳出力 (`<動画ID>.highlights.compiled.md`)**: 複数本まとめてAIに読み込ませる横断分析にも対応した調査メタデータ付き台帳ファイルを、一次資料・AI生成物区別ルールに沿って出力します。
- **Fandom Wiki ソース紐づけ＆知見蓄積**: 話題に出た過去企画や設定を Fandom Wiki と照合し、分析で得た知見を `references/shizuku-knowledge.md` に、進捗を `references/analyzed-logs.md` に蓄積します。

## 構成ファイル

- `SKILL.md`: スキル本体
- `scripts/mine_highlights.py`: 字幕（`sbv` / `.srt`）・画面OCR（`screen-ocr`）・チャット前処理＋AI語2段階スパイク・物語区間候補の自動抽出スクリプト
- `references/extraction-guide.md`: 6カテゴリの抽出基準、`screen-ocr` 3層照合ルール、Fandom Wiki 照合ルール、台帳ファイル出力ガイド、Discord 2,000文字分割ガイド
- `references/shizuku-knowledge.md`: AIしずくの蓄積知見（設定・口癖・TTS/ASR癖・主要エピソード・Fandom Wiki URL一覧）
- `references/analyzed-logs.md`: 時系列ログ分析トラッカー（重複分析防止リスト）

## 前処理と出典の確認

リポジトリのルートから実行する。出力先には配信フォルダの外の作業先を使う。省略時は一時フォルダを新規に作る。

```powershell
python -X utf8 tools/skills/youtube-highlight-miner/scripts/mine_highlights.py "<配信フォルダ>" --out-dir "outputs/highlights/<動画ID>"
```

- `timeline.txt` は音声字幕、画面OCR、文脈用のチャットを時刻順に1回ずつ載せる。チャットは従来どおり時間帯ごとに最大10件。画面OCRの時刻はミリ秒を保持する。
- `ocr-evidence.json` は各O番号に対応する元ファイル、行、時刻、照合できたフレームを保持する。複数行の1観測を分けた場合は `part` が元の表示行順。連続表示や周回をまとめた数は画面の観測数で、発話回数の根拠には使わない。
- 同じ動画の `verification.json` に載った保存本文のSHA-256が一致する場合は、記録済みのフレームを自動で使う。手動指定は `--frames <frames.jsonl>` を時間順に繰り返す。フレームがない場合や `--no-frames` を指定した場合は、OCR本文を保持し、短時間の文字列反復だけを再表示候補として扱う。
- 通常表示、周回表示、言い直しを含む同一入力で改訂を比べる。根拠時刻・要確認・新しい発言の保持と、旧版からの重複・実トークン数の変化を確認する。

## 更新履歴

- **v1.5.0**: 通読と照合の入力を統合し、画面OCRの再表示の根拠と横断分析用のURL短縮を追加。

- **v1.4.0**: `persona`・`shizuku-pipeline` の知見を取り込み、プロフィール・性格・個性（新規/強化/揺れ・`[TTL: 短期]`）、機能・挙動（`capability`）、未回収ネタ（`open_loop`）を追加。1配信20〜25項目（4〜6KB）のサイズ制御ルールを導入。
- **v1.3.0**: 配信フォルダ内での管理用台帳ファイル出力ルール（`<動画ID>.highlights.compiled.md`＋調査メタデータ必須ヘッダ）を追加。
- **v1.2.0**: `screen-ocr.txt` 統合・3層切り分け（ASR誤認 / TTS崩れ / AIテキスト挙動）を追加。`references/shizuku-knowledge.md` と `references/analyzed-logs.md` を新設し、2023-01-19 (`YuJ4oOGNGxg`) の知見を反映。
- **v1.1.0**: AI語・空耳反応を `🟢高確度 / 🟡候補` の2段階分類に変更し、直前45秒の他言語質問・フリ検出と観測ベース表記を追加。
- **v1.0.0**: 初版リリース。
