# YouTubeコメント用タイムスタンプ (`youtube-timestamp-comment`)

YouTube配信の字幕（`sbv`）・ライブチャット（`live_chat` / `live_chat_ocr`）・動画情報（`info`）・コメント（`comments`）から、視聴者が思わずクリックしたくなる「予告（Teaser）型」のコメント用タイムスタンプ目次を作成するスキルです。

## 構成ファイル

- `SKILL.md`: スキル本体（トリガー条件・ワークフロー・シーン説明ルール・出力形式）
- `scripts/build_timeline.py`: 分割されたSBVとチャットを突き合わせる前処理スクリプト（Python標準ライブラリのみで動作）
- `references/editorial-craft.md`: トーン調整・NGワード回避・AI臭さ排除・外部調査・対話チューニング・双方向照合のガイド
- `references/shizuku-profile.md`: 配信者「しずく」固有の誤変換辞書・定型句リファレンス
- `references/existing-timestamps.md`: 既存目次の充実度判定・手動投稿後の3分待機と公開確認手順
- `references/command-driven-chat.md`: クイズ・ゲーム等の `@` / `#` コマンド制配信のチャット解釈ルール

## 運用環境とオプション

- **単体環境（クラウド／ファイル添付）**: 対象動画のログファイルを指定して `scripts/build_timeline.py` で前処理し、チャットに直接タイムスタンプ目次を出力します。
- **リポジトリ環境**: ローカルリポジトリの `tools/scripts/check_youtube_timestamps.py` と連携し、保存済みコメントの確認・再取得・`outputs/youtube-timestamps/status/<動画ID>.json` による投稿後フォローまで一貫して行えます。
- **トーン・NGワード指定**: 既定ではストレートなリスナー目線（`standard`）で即生成します。依頼時に「やわらかめで」「面白さ重視で」「固めで」「NGワード: 〇〇」のように指定すると文体や語彙を調整します。

※ YouTubeとFandom「動画・配信」の一覧照合、未収録ログの収集、Wiki編集は別スキルの範囲であり、このスキルには含めません。
