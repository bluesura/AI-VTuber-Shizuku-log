---
name: youtube-highlight-miner
description: YouTube配信ログから、プロフィール・機能・口癖・AI語・名言・物語を発掘し、根拠時刻とFandom参照を付けた配信分析台帳やDiscord共有文にまとめる。配信の目次作成は youtube-timestamp-comment を使う。
---

# YouTube配信ログのハイライトと分析台帳 (v1.5.0)

## 入力と通読

1. 同じ動画IDの動画情報、音声字幕（SBV優先、SRT代替）、画面OCR、チャット、事後コメントを確認する。比較用ASRがあれば聴取確認の補助に使う。
2. `python scripts/mine_highlights.py <配信フォルダ> --out-dir <作業先>` を実行し、`timeline.txt` を最初から時刻順に読む。長い入力は時刻範囲で分けて最後まで進む。候補区間は探索の補助に使う。
3. `SUB` は音声字幕、`O` 番号は画面OCR、`CHAT` は文脈用。元資料や `ocr-evidence.json` は引用、誤読、区間境界の確認に使う。保存済みフレームの使い方は [README](README.md) を参照する。

## 根拠と抽出

- [抽出・照合ガイド](references/extraction-guide.md) の6カテゴリに分類する。自発発言と誘導、AI語の高確度と候補、長期の特性とその場の発言を区別する。未回収ネタには回収と判断できる条件を添える。
- OCRの連続表示・周回を発言回数へ足さない。`再表示候補` や `要確認` の行を引用・高確度の根拠に使う前に元画面を確認する。画面表示、ASR誤認、TTSの読み上げは画面と音声で照合する。他言語の返答は直前の質問も確認する。
- 時刻は音声字幕・画面OCRで照合し、ジャンプ先は会話の入り（オチの1〜5秒前を目安）に置く。URLは `&t=<秒数>s` を付ける。視聴者の名前は出力しない。
- 既知の設定・用語との照合には [しずく知見ベース](references/shizuku-knowledge.md) を、処理済みの確認には [分析済みログ一覧](references/analyzed-logs.md) を使う。FandomのURLは確認できたものだけを載せる。

## 保存と共有

- 1配信20〜25項目を目安に `<動画ID>.highlights.compiled.md` へ保存する。引用の文脈、根拠、クリック可能なURL、AI生成・未確認の表示を保つ。台帳テンプレートやDiscord共有形式は [抽出・照合ガイド](references/extraction-guide.md) の§5–6を使う。
- 横断分析に複数台帳を渡すときは `python scripts/compact_ledgers.py <台帳> ...` で同一動画URLだけを短縮する。出力中の時刻リンクは各台帳の動画IDから復元できる。
