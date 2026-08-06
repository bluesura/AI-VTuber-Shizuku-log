# 動画時間収集スキル

YouTubeや、`yt-dlp`が対応する各種動画サイトのURLから、動画本体をダウンロードせずに再生時間を集め、`H:MM:SS`形式の表・CSV・TSV・JSONにします。

## 特徴

- YouTube Data APIが使える場合は、動画IDを最大50件ずつ一括取得
- APIキーがない場合や他サイトでは`yt-dlp`でメタデータのみ取得
- 最後の手段として、ページ内のYouTube `lengthSeconds`、JSON-LD、`og:video:duration`を解析
- 入力順を維持しつつ、重複URLへのネットワークアクセスは1回に集約
- 確定済みVODだけを任意のJSONキャッシュへ保存
- 非公開、削除、ログイン必須、ライブ中、配信予定、処理中を明示
- 取得成功分だけの合計時間を表示

## セットアップ

Python 3.10以上を利用します。YouTube以外も広く扱う場合、またはYouTube APIキーを使わない場合は`yt-dlp`をインストールしてください。

```bash
python -m pip install -U yt-dlp
```

YouTube Data APIを使う場合は環境変数を設定します。

```bash
export YOUTUBE_API_KEY="YOUR_KEY"
```

Windows PowerShell:

```powershell
$env:YOUTUBE_API_KEY = "YOUR_KEY"
```

## 基本的な使い方

URLを直接渡す:

```bash
python scripts/collect_video_durations.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  "https://vimeo.com/VIDEO_ID"
```

1行1URLのテキストファイルから取得:

```bash
python scripts/collect_video_durations.py --input examples/urls.txt
```

CSVへ保存:

```bash
python scripts/collect_video_durations.py \
  --input examples/urls.txt \
  --format csv \
  --output durations.csv
```

JSONキャッシュを利用:

```bash
python scripts/collect_video_durations.py \
  --input examples/urls.txt \
  --cache .video-duration-cache.json
```

ログインが必要で、かつ自分に閲覧権限があるページをブラウザのCookieで取得:

```bash
python scripts/collect_video_durations.py \
  --input private_urls.txt \
  --cookies-from-browser chrome
```

## バックエンド

`--backend auto`が既定です。

| 値 | 動作 |
|---|---|
| `auto` | YouTube API → yt-dlp → HTMLメタデータ |
| `youtube-api` | YouTube Data APIのみ |
| `yt-dlp` | yt-dlpのみ |
| `html` | ページ内メタデータのみ |

## 出力形式

```bash
--format markdown
--format csv
--format tsv
--format json
```

CSVはExcelで開きやすいUTF-8 BOM付きで保存します。

## 主なオプション

```text
--workers 6                 並列数
--timeout 20                1リクエストのタイムアウト秒
--cache FILE                成功済みVODのキャッシュ
--cache-ttl 86400           キャッシュ有効期間。0は無期限
--cookies-from-browser NAME 閲覧権限のあるページ用
--yt-dlp-arg=VALUE          yt-dlpへ追加引数を渡す
```

## 終了コード

- `0`: 全URLの動画時間を取得
- `2`: 1件以上が未取得、ライブ中、配信予定、処理中、またはエラー

表やCSVは終了コードが`2`でも生成されます。

## テスト

```bash
python scripts/test_collect_video_durations.py -v
```

外部ネットワークを使わずに、URL解析・時間変換・HTMLメタデータ・キャッシュ・出力を検証します。

## 重要な運用ルール

検索結果のスニペット、チャンネル一覧、別動画へのリンクを根拠に動画時間を決めません。正確な値を取得できなかった行は空欄にし、理由を明記します。
