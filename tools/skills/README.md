# スキル一覧

各フォルダ直下の `SKILL.md` がスキルの入口です。リポジトリ内では、対象の `SKILL.md` と作業に必要な参照資料をその場で読んで使えます。

| 作業 | 利用案内 | スキル本体 |
|---|---|---|
| しずくのFandom Wikiを調査し、差分を提案・反映する | [しずくWiki編集](shizuku-wiki/README.md) | [shizuku-wiki](shizuku-wiki/SKILL.md) |
| YouTubeなどの動画URLから再生時間を集める | [動画時間収集](video-duration-collector/README.md) | [video-duration-collector](video-duration-collector/SKILL.md) |
| 配信ログからYouTubeコメント用の目次を作る | [YouTubeコメント用タイムスタンプ](youtube_timestamp_comment_skill/README.md) | [youtube-timestamp-comment](youtube_timestamp_comment_skill/SKILL.md) |

Wikiの「動画・配信」の一覧照合、URLからの再生時間取得、コメント用の目次作成は、それぞれ独立した作業です。ログの収集や字幕の補完は、リポジトリの案内を参照してください。[リポジトリのREADME](../../Readme.md)

## 別の環境で使う

利用先がフォルダでの導入に対応していれば、対象スキルのフォルダを参照資料や同梱スクリプトごと導入します。タイムスタンプ作成スキルの名前は `youtube-timestamp-comment` です。導入先でスキル名とフォルダ名を揃える場合は、この名前で配置してください。

`.skill` が必要な環境では、用途に応じて正本から配布用ファイルを作成します。Wiki編集スキルのZIP形式と同梱対象はスキル本体の「作業のあとに」を参照してください。[shizuku-wikiの配布手順](shizuku-wiki/SKILL.md#6-作業のあとに--振り返りとスキルの更新)

タイムスタンプ作成で保存済みコメントの確認や再取得に使う補助コマンドは、リポジトリ側の `tools/scripts/` にあります。個別の依存関係とコマンドの実行場所は、各READMEを参照してください。
