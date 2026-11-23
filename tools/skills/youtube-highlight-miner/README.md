# YouTubeハイライト・配信分析台帳採掘 (`youtube-highlight-miner`)

**Current Version: v1.4.0**

`youtube-timestamp-comment` から派生した、配信ログ分析・ネタ採掘・配信分析台帳作成特化スキルです。

## 特徴

- **6カテゴリ採掘＆サイズ制御**: 配信者の「プロフィール・性格・個性（新規/強化/揺れ・`[TTL: 短期]`）」「機能・システム挙動」「癖・口癖」「AI語・謎言語」「名言・迷言」「一連の流れ・物語＆未回収ネタ（`open_loop`）」を、1配信20〜25項目目安（4〜6KB）のコンパクトな粒度で抽出します。
- **画面OCR (`screen-ocr.txt`) による高精度切り分け**: 画面内テキストボックスのOCR結果を活用し、「YouTube ASRの誤認識」「TTS（COEIROINK等）の読み上げ崩れ」「AI本体のテキスト生成バグ・言い間違い」を正確に切り分けます。
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

## 更新履歴

- **v1.4.0**: `persona`・`shizuku-pipeline` の知見を取り込み、プロフィール・性格・個性（新規/強化/揺れ・`[TTL: 短期]`）、機能・挙動（`capability`）、未回収ネタ（`open_loop`）を追加。1配信20〜25項目（4〜6KB）のサイズ制御ルールを導入。
- **v1.3.0**: 配信フォルダ内での管理用台帳ファイル出力ルール（`<動画ID>.highlights.compiled.md`＋調査メタデータ必須ヘッダ）を追加。
- **v1.2.0**: `screen-ocr.txt` 統合・3層切り分け（ASR誤認 / TTS崩れ / AIテキスト挙動）を追加。`references/shizuku-knowledge.md` と `references/analyzed-logs.md` を新設し、2023-01-19 (`YuJ4oOGNGxg`) の知見を反映。
- **v1.1.0**: AI語・空耳反応を `🟢高確度 / 🟡候補` の2段階分類に変更し、直前45秒の他言語質問・フリ検出と観測ベース表記を追加。
- **v1.0.0**: 初版リリース。
