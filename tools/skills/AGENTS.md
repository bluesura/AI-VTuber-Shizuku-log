# AGENTS.md — tools/skills

`tools/skills/` 以下に適用し、[リポジトリ共通の指示](../../AGENTS.md) を補足します。

## 最初に読むもの

[スキル一覧](README.md) から作業対象を選び、そのフォルダ直下の `SKILL.md` と `README.md` を読みます。Wiki編集では、対象ページの手順と [Wiki編集スキル固有の指示](shizuku-wiki/AGENTS.md) も確認します。

- `shizuku-wiki/` はFandom Wikiの調査・提案・反映を担当します。依頼文の例は [プロンプトパターン集](shizuku-wiki/PROMPT_PATTERNS.md) にあります。
- `video-duration-collector/` は動画URLから再生時間を取得する独立したスキルです。CLIと同梱ファイルの一覧は [README](video-duration-collector/README.md) と [manifest.txt](video-duration-collector/manifest.txt) を参照します。
- `youtube_timestamp_comment_skill/` はタイムスタンプコメントの作成と手動投稿後の確認を担当します。コメント確認の補助スクリプトはリポジトリ側にあります。[既存目次と投稿確認の手順](youtube_timestamp_comment_skill/references/existing-timestamps.md)

## 保守と検証

- 各スキルの正本は、`SKILL.md` があるフォルダです。名前や配置を変えた場合は、ルート文書や関連手順からのリンク、コマンドの実行場所、同梱ファイル一覧も確認します。
- 配布用ファイルを作る場合は対象スキルの正本を使い、展開後の構成と内容を確認します。ログ原本、認証情報、作業出力、キャッシュは配布対象から除外します。導入先への同期は実際に確認できた範囲で報告します。
- 文書変更では相対リンクとコマンドの参照先を確認します。`SKILL.md` を変更した場合は、利用できる環境では `skill-creator` の `quick_validate.py` に対象スキルのフォルダを渡して検証します。検証ツールの場所は実行環境に合わせます。

関連スクリプトを検証する場合は、リポジトリのルートから対象に応じて実行します。

```powershell
python -X utf8 -m unittest discover -s tools/skills/shizuku-wiki/scripts -p "test_*.py"
python -X utf8 -m unittest discover -s tools/skills/video-duration-collector/scripts -p "test_*.py"
python -X utf8 -m unittest discover -s tools/scripts -p "test_check_youtube_timestamps.py"
```
