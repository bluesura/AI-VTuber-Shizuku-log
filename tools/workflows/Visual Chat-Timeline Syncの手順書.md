# YouTubeライブチャット 自動文字起こし手順（完全版）

YouTubeのライブ配信アーカイブからチャット部分の画像を抽出し、Pythonスクリプトで前処理を行った後、Google AI Studio（Gemini Pro）を利用して、重複のないタイムスタンプ付きテキストに変換するための全ワークフローです。

## ローカルOCRで画面の発言欄を読む

`ocr_youtube_overlay.py` は、対象の枠を切り抜き、画面に変化があった画像をCPUでOCRします。認識結果の語句はそのまま記録します。別のチャットから続けるときは [進行チェックリスト](screen_ocr_progress.md) と [再開プロンプト](../prompts/screen_ocr_resume.prompt.md) を使います。

### 準備と映像の取得

リポジトリのルートで作業します。FFmpeg、ffprobe、yt-dlpをPATHに用意し、すでにある `outputs/shizuku-screen-ocr/venv/Scripts/python.exe` と `outputs/shizuku-screen-ocr/models/` を再利用します。仮想環境がない場合の準備は次のとおりです。OCRモデルは初回実行時に取得します。

```powershell
python -m venv outputs/shizuku-screen-ocr/venv
& 'outputs/shizuku-screen-ocr/venv/Scripts/python.exe' -m pip install 'rapidocr==3.10.0' onnxruntime
```

対象の `.info.txt` で動画IDとURLを確認します。以下は720pまでの映像を取得する例です。対象の文字が小さければ、短い区間で読みやすさを比べて映像の解像度を決めます。`source.mkv` がある場合は `ffprobe` で解像度と再生時間を確認して再利用します。

```powershell
$videoId = '対象の動画ID'
$work = "outputs/shizuku-screen-ocr/$videoId"
$python = 'outputs/shizuku-screen-ocr/venv/Scripts/python.exe'
$layout = "tools/scripts/screen_ocr_layouts/$videoId.json"
New-Item -ItemType Directory -Force -Path $work | Out-Null
if (-not (Test-Path -LiteralPath "$work/source.mkv" -PathType Leaf)) {
    yt-dlp --ignore-config --no-playlist --continue -f 'bv[height<=720]/b[height<=720]' --remux-video mkv -o "$work/source.%(ext)s" "https://www.youtube.com/watch?v=$videoId"
}
ffprobe -v error -select_streams v:0 -show_entries 'stream=width,height:format=duration' -of json "$work/source.mkv"
```

### レイアウト確認と実行

JSONの `video_id` と `size` を対象に合わせ、`crop` に `[左, 上, 幅, 高さ]` をピクセルで指定します。画面構成が変わる動画は `start_ms` と `end_ms` を付けて `regions` を時間帯ごとに並べます。内容が入れ替わる発言枠は `mode: "replace"`、行が上に流れる欄は `mode: "scroll"` を候補にします。白地に黒字の水平な字幕枠では `dark_on_light: true` で行を切り出して認識できます。

```powershell
# 実際に発言欄に文字が表示される時刻に変更する。
& $python tools/scripts/ocr_youtube_overlay.py "$work/source.mkv" --layout $layout --start-ms 120000 --end-ms 130000 --workdir "$work/pilot-120"
# 切り抜き画像と認識結果の確認後、新しい作業フォルダに出力する。
& $python tools/scripts/ocr_youtube_overlay.py "$work/source.mkv" --layout $layout --workdir "$work/full"
```

- `<動画ID>.screen-ocr.txt` は動画時刻付きの統合テキストです。白地に黒字の枠では字形が続く間の読みをまとめ、OCRで最も多く出た表記を載せます。`[要確認]` はスコアが低い箇所、同じ表示で読みが割れた箇所、英語の `l`/`I` 混同が疑われる箇所を示します。時刻は採用した文字列を読んだフレームの位置です。
- `frames.jsonl` に動画時刻、OCRを行った理由、文字列、スコア、切り抜き内の座標と画像名が残ります。`frames/` のPNGは確認用です。視聴者名を含む画像や生の認識結果は作業フォルダで扱います。
- `--start-ms` と `--end-ms` で短い区間から試せます。既定の毎秒4枚で短い表示を落とす場合は `--fps` を上げます。`--all-frames` は間引きの影響を測る試験用です。処理枚数と時間は `stats.json` に記録します。

### レイアウトと対象枠の決め方

- 枠の位置は動画ごとに確認します。同じチャンネルでも配信ごとに配置が変わるため、別動画の `crop` を流用しません。
- しずくの発言欄が複数ある画面では、いちばん大きい「現在の発言欄」だけを対象にします。上に小さく残る「前回の発言」欄をcropに含めると、同じ文が二重に出ます。
- 行の高さを実測し、`crop` の高さを「行数×行高＋余白」に合わせます。全画面座標で測った行の上端・下端を基準に、上下へ8px程度の余白を入れます。
- `--start-ms` と `--end-ms` で数秒だけ処理し、切り抜き画像と認識結果を目視してから全体を回します。切り抜きの位置ずれは、全体処理後の修正では気づきにくくなります。
- 待機画面・場面転換・終幕が混ざると、キャラクターの頭や周囲のUIを文字として読むことがあります。冒頭と終幕の切り替えを実映像で確かめ、発言欄のある時間帯をレイアウトJSONの `start_ms` / `end_ms` で指定します。すでに処理した映像は、元の `frames.jsonl` を保持し、該当する時間帯の行だけを別のマニフェストに抽出して再集約できます。
- 枠の端で切れた10px程度の帯は、縦横比が極端になり認識できないため自動で除外されます。細い帯が残って `stats.json` の処理枚数が不自然に多い場合は、cropを見直します。
- 枠の縁やアバターの動きがOCR件数を増やすときは、行末まで見える範囲でcropを調整します。2月4日の試行では、右端を8px狭めると同じ105サンプルのOCR対象が84枚から8枚になり、目視した2件の返答を拾えました。本編のスクロール中の断片や重複は検証記録に残しています。

### 中断からの再開

| 確認した状態 | 再開する操作 |
| --- | --- |
| 動画フォルダに `.screen-ocr.txt` がある | 本文の動画ID・時刻順・保存範囲を確認します。`verification.json` がある場合は出力SHA-256を照合します。確認画像や検証記録が別環境にある場合は、本文の保存と手元で確認できた範囲をチェックリストに記録します。 |
| `.part` があり、映像の取得が中断している | 同じ動画・形式・出力名で `yt-dlp --continue` を使います。取得が進行中なら、その実行を待ちます。 |
| `source.mkv` と設定JSONがある | `ffprobe` の結果と対象範囲を確認して再利用します。短い試行済みなら、次の工程をチェックリストから確認します。 |
| 対象範囲の `stats.json`、`frames.jsonl`、出力本文がそろっている | `stats.json` のOCR枚数とマニフェスト行数、対応するPNG、対象範囲を照合します。結果を再利用して検証から続けます。再集約だけ必要なら、`ocr_youtube_overlay.py` の `write_timeline(manifest, timeline, video_id)` を新しい出力先に対して使えます。 |
| `frames.jsonl` はあるが、その区間が正常終了していない | 部分結果を調査用に保持します。OCRスクリプトは既存の `--workdir` に追記しないため、中断した区間だけを新しい作業フォルダで実行します。 |

### 長時間配信を区間ごとに処理する

12時間近い耐久配信は、同じ `source.mkv` とレイアウトJSONから、30〜60分程度を目安に `--start-ms` / `--end-ms` で分割します。実行前に対象の開始・終了時刻と区間ごとの作業フォルダを記録します。たとえば最初の30分なら `--start-ms 0 --end-ms 1800000 --workdir "$work/part_000000_1800000"` を指定します。実際の開始は発言欄が出る時刻に合わせます。区間は開始を含み、終了を含みません。出力時刻は動画全体の基準なので、区間の開始時刻を再度足す必要はありません。

発言欄が空の位置を境界にできれば、同じ発言を途中で分けるのを避けられます。発言中に分割した場合は、境界の前後を元画像で見比べ、重複や欠落を確認します。判断しづらい場合は前後の短い区間を別フォルダでOCRして照合します。各区間の `stats.json` と出力を確認したら、作業フォルダと完了した時刻範囲を記録します。全範囲がそろった時点で、時刻順に各本文を統合し、見出しは先頭に一組だけ残します。`verification.json` には対象範囲と各区間のマニフェストの対応も記録します。

### 発言の再構成

- 発言欄は1件ずつ表示され、消えると次の発言まで間が空きます。20〜40秒の空白は欠落とは限りません。
- 長い発言は行単位で上へ流れ、途中で次の発言に切り替わると先頭・末尾が欠けます。表示単位の出力に断片や重複が多い場合は、保存した `frames.jsonl` を読み、隣接フレームで行が重なる範囲を確認して別の候補へ連結します。再構成の範囲・前提・確認したフレームを記録します。
- 再構成では、行の高さを測って枠の縁で欠けた行を見分けます。1月28日と29日の再構成に使った補助処理と設定は各動画の作業フォルダと検証記録にあります。`outputs/` を引き継げない環境でも、リポジトリの `ocr_youtube_overlay.py` で通常の表示単位のOCR結果を作れます。再構成で判断できない語句や行の順序には `[要確認]` を残します。
- 読みが割れた行、スコアの低い行、英語の `l`/`I` 混同（`wiII` など）は `[要確認]` にします。`プ口グラム`、`才ーラカ`、`協カ`、`ゲ一ム`、`I0個`、`ー緒` のような誤認識は勝手に直さず、本文はOCRの読みのまま残して確認対象にします。
- 4fpsでは0.5秒未満の表示を取りこぼすことがあります。短い表示が多い配信では `--fps` を上げ、`stats.json` の処理枚数と所要時間を確認します。

### 仕上がりの確認

- 最初と最後の発言、いちばん長い発言、英語の発言、`[要確認]` のいくつかをフレーム画像で読み直します。
- 保存する候補の件数・行数・`[要確認]` 件数を数えます。区間の除外や再構成があった場合、処理時の `stats.json` と最終候補の件数が異なることがあります。`verification.json` に元URL、公開日、映像取得・OCR生成日時、元動画と保存本文のSHA-256、crop、fps、対象範囲、ツールとモデルの版、確認したフレーム、既知の誤認識を残します。
- 出力はUTF-8（BOMなし）・LFとします。検証した候補を `.info.txt` と同じ動画フォルダに `<動画ID>.screen-ocr.txt` として追加します。既存本文がある場合は照合し、再処理を明示された場合も別の候補を作業フォルダに作ります。保存本文のハッシュを再確認して [進行チェックリスト](screen_ocr_progress.md) を更新します。

---

## 事前準備

各種ツールのインストールと、作業用ディレクトリの作成を行います。

### 必要なツールのインストール

```bash
# YouTubeダウンロードツール
pip install yt-dlp

# Pythonの画像処理ライブラリ
pip install Pillow

# FFmpeg（OSに合わせてインストール）
# Windows (Winget):
winget install ffmpeg
# Mac (Homebrew):
brew install ffmpeg
```

### ディレクトリ構成の準備

作業用ディレクトリに移動した上で、以下のコマンドを実行してフォルダを一括作成します。

```bash
# Windows (cmd / PowerShell)
mkdir frames thinned combined

# Mac / Linux
mkdir -p frames thinned combined
```

| フォルダ名 | 用途 |
| --- | --- |
| `./frames` | 抽出した1秒ごとの元画像を格納 |
| `./thinned` | 間引き後の画像を格納 |
| `./combined` | 結合後の画像を格納 |

---

## Step 0: 前処理 — 動画のダウンロードと画像の抽出

YouTubeから動画をダウンロードし、1秒に1枚のペースで画像を切り出します。

### ① 動画のダウンロード（yt-dlp）

```bash
# 動画と音声を最高画質/音質でダウンロードし、MKV形式で保存する
yt-dlp -f "bestvideo+bestaudio/best" --merge-output-format mkv -o "input.mkv" [YouTubeのURL]
```

> **注意:** `ba[ext=m4a]` は音声のみの指定となるため、映像を含む上記コマンドを使用してください。

---

#### トラブルシューティング：ダウンロードが途中で止まる場合

**問題**

`yt-dlp` でYouTube動画をダウンロードしようとしたが、映像ストリーム（`f399.mp4`）が途中で止まり `.mkv` が生成されなかった。

**原因**

- YouTubeのCDNサーバー（`rr2---sn-vjoouujvhh-nqwe.googlevideo.com`）が HTTP 503 でブロック
- 並列ダウンロード（aria2c）では503が多発して停止する
- JSランタイム（deno）未インストールのため、webクライアントでフォーマット一覧すら取得不可
- MP4はファイル末尾に索引（moovアトム）があるため、途中ファイルはそのままでは再生不可

**試したが効果がなかった方法**

| 方法 | 結果 |
| --- | --- |
| `--http-chunk-size 10M` | 53%で止まる |
| `--force-ipv4` | URLにIPv6が埋め込み済みで無効 |
| `--retries 20` | 回数を増やしても同じ箇所で失敗 |
| `--cookies-from-browser chrome` | Chromeのクッキー取得エラー |
| `player_client=web` | JSランタイムなしで動画フォーマット取得不可 |

**✅ うまくいった方法**

**aria2cで98%までダウンロードする**

```cmd
winget install aria2.aria2

yt-dlp --downloader aria2c --downloader-args "aria2c:-x 16 -s 16 -k 5M" https://www.youtube.com/watch?v=zZDlC3BcQ2M
```

→ 98%で503エラーにより停止。`.part` ファイルが残る。

**ffmpegで部分ファイルを再生可能なMP4に変換する**

```cmd
ffmpeg -fflags +genpts+discardcorrupt -i "ファイル名.f399.mp4.part" -i "ファイル名.f251.webm" -c copy -movflags faststart "output_partial.mp4"
```

→ 98%分の映像＋音声付きMP4として再生成功。

---

### ② 動画から画像への抽出（ffmpeg）

```bash
# MKV動画から「1秒に1枚（fps=1）」のペースで連番のJPG画像を出力する
mkdir frames
ffmpeg -i input.mkv -vf fps=1 "frames/%04d.jpg"
```

> **ポイント:** 1秒に1枚出力されるため、ファイル名の連番（`0001.jpg`、`0002.jpg`…）がそのまま**動画の経過秒数（タイムスタンプ）**と連動します。

---

## Step 1: `thinning.py` による画像の間引き

画像が多すぎるため、画面のスクロール速度に合わせてコメントがこぼれない間隔で画像を抽出します。チャットの流速「12秒で約2行」に合わせ、15秒間隔を採用しています。

```bash
# 15フレーム（15秒）に1枚の割合で間引く
python thinning.py --input ./frames --output ./thinned --interval 15
```

**結果:** 約3,800枚の画像が **約250枚** に削減され、`./thinned` に出力されます。

> 間引き後、IrfanViewなどのソフトウェアで所定の箇所をトリミングしてください。

---

## Step 2: `combine.py` による画像の結合とタイムスタンプ焼き込み

AIの横読み防止のための「区切り線」と、文字起こし用の「タイムスタンプラベル」を画像自体に描画して横に結合します。

```bash
# デフォルト設定で結合（5枚結合・区切り線4px・薄グレー）
python combine.py --input ./thinned --output ./combined
python combine.py --input ./thinned --output ./combined --interval 15
python combine_fixed.py  --input ./thinned  --output ./combined  --per-row 5  --wide-per-page 5  --interval 15
```

**結果:** 約250枚の画像が **約50枚の結合画像** にまとまり、各コマの上に `[0:00:00]`、`[0:00:15]` などのタイムスタンプが焼き込まれて `./combined` に出力されます。

**結合画像のイメージ:**

```
┌─[0:00:00]─┬─[0:00:15]─┬─[0:00:30]─┬─[0:00:45]─┬─[0:01:00]─┐
│  チャット  │  チャット  │  チャット  │  チャット  │  チャット  │
│   画面     │   画面     │   画面     │   画面     │   画面     │
└───────────┴───────────┴───────────┴───────────┴───────────┘
```

---

## Step 3: Google AI Studio での文字起こし

加工が完了した画像をAI Studioに投入し、文字起こしを行います。

1. Google AI Studioのチャット画面を開く
2. `./combined` フォルダ内の画像（約50枚）を**すべて一括でアップロード**する
3. 以下のプロンプトを入力して実行する

### 入力プロンプト

```
各画像の上部には区画ごとのタイムスタンプが記載されています（例: [1:02:30]）。
これらはYouTubeライブチャットの画面を時系列順に横に並べたスナップショットです。

以下のルールに従ってコメントを文字起こしてください。

【ルール】
- 縦線で区切られた各区画を左から順に独立したチャット画面として読み取る
- 各コメントが「初めて画面に登場した」区画のタイムスタンプを先頭に付ける
- 同じコメントが複数の区画にまたがっていても1回だけ出力する（初出区画で処理）
- ユーザー名は @ を付けてそのまま記載する
- 読み取れない文字は [?] と記載する
- チャット以外のUI要素（バッジ・アイコン説明など）は出力しない

【出力形式】（1コメント1行）
[H:MM:SS] @ユーザー名: コメント本文
```

---

以上の手順により、ダウンロード → 画像切り出し → 自動前処理 → AIによる文字起こしまでの全工程がシステム化されます。
