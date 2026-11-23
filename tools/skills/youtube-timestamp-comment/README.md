# YouTubeコメント用タイムスタンプ (`youtube-timestamp-comment`)

**Current Version: v2.1.0**

YouTube配信の字幕（`sbv` 優先、無ければ `.srt`）・ライブチャット（`live_chat` / `live_chat_ocr`）・動画情報（`info`）・コメント（`comments`）から、見やすくクリックしたくなるコメント用タイムスタンプ目次を作成するスキルです。

## 構成ファイル

- `SKILL.md`: スキル本体（即生成／対話選択の分岐、ワークフロー、出力形式、コメント自動分割）
- `scripts/build_timeline.py`: 分割された字幕とチャットを突き合わせる前処理スクリプト（Python標準ライブラリのみで動作、`.srt` フォールバック対応）
- `references/editorial-craft.md`: 5つの型、7つの調整軸（装飾・絵文字・ファンマーク・文字数・言語等）、基礎テクニック、grilling対話、双方向照合ガイド
- `references/shizuku-profile.md`: 配信者「しずく」固有の誤変換辞書・定型句リファレンス
- `references/custom-notes.md`: ユーザー指示による汎用知見・好みの蓄積リファレンス（蓄積が進めば専門リファレンスへ分離）
- `references/existing-timestamps.md`: 既存目次の充実度判定・手動投稿後の3分待機と公開確認手順
- `references/command-driven-chat.md`: クイズ・ゲーム等の `@` / `#` コマンド制配信のチャット解釈ルール

## 更新履歴（Changelog）

- **v2.1.0**: バージョン管理を導入。パターンA末尾のおすすめ提案、パターンBの `grilling` ラウンド制対話、特殊性癖特化・区間ネタバレゼロ型、装飾/絵文字/ファンマーク/文字数3段階/言語併記/感想添えオプション、基礎テクニック整理、`custom-notes.md` を追加。
- **v2.0.0**: 「さくっと」即生成 vs 選択肢提示の分岐、コメント自動分割、`.srt` フォールバック、`editorial-craft.md`（AI臭さ排除・双方向照合）を統合。
- **v1.1.0**: `build_timeline.py` の `scripts/` 外出し、`shizuku-profile.md` 分離、180行へのスリム化、`MM:SS` 形式統一。
