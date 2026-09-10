# shizuku-wiki

AI VTuber「しずく」の[Fandom Wiki](https://shizuku.fandom.com)を、一貫したルールで編集するためのAIエージェント向けスキル。

このWiki自体は公式が管理するファンダムWikiです。本スキルおよびこのGitHubリポジトリで公開している編集ログ等の更新作業は、有志による非公式の取り組みです。

---

## これは何か

Wikiの編集をLLMに手伝わせると、日付の書き方が毎回違ったり、同じ出典に別の名前が付いたり、外部リンクの構文が壊れたりします。原因は「同じルールが複数の場所に別の言葉で書かれている」ことです。

このスキルは、しずくWikiの編集ルールを1箇所に集約したものです。

- **どのページに何を書くか**の振り分け
- **日付・出典・MediaWiki記法**の共通ルール
- **ページごとの更新手順**（6ページ分）
- **トーン・文体**のガイド
- **日英翻訳**の語彙集
- **モニタリング**の運用手順

---

## インストール

### Codex / Claude.ai / Claude Desktop

`shizuku-wiki.skill` をダウンロードし、チャットに添付して「Save skill」を押します。

### Claude Code

スキルフォルダを配置します。

```bash
git clone https://github.com/<your-account>/shizuku-wiki.git ~/.claude/skills/shizuku-wiki
```

`.skill` ファイルはzip形式なので、拡張子を `.zip` に変えれば中身を直接展開できます。

### 動画・配信ページの自動更新

確認処理は公開APIを匿名で読み取ります。承認後の反映に使う認証情報はリポジトリやチャットへ保存せず、次のユーザー環境変数に設定します。

```text
SHIZUKU_FANDOM_BOT_USERNAME
SHIZUKU_FANDOM_BOT_PASSWORD
```

PowerShellでは、値をコマンド履歴へ直接書かないよう次のように設定できます。

```powershell
$shizukuBotUser = Read-Host "Bot PasswordのUsername"
$shizukuBotSecure = Read-Host "Bot Password" -AsSecureString
$shizukuBotPassword = [Net.NetworkCredential]::new("", $shizukuBotSecure).Password
[Environment]::SetEnvironmentVariable("SHIZUKU_FANDOM_BOT_USERNAME", $shizukuBotUser, "User")
[Environment]::SetEnvironmentVariable("SHIZUKU_FANDOM_BOT_PASSWORD", $shizukuBotPassword, "User")
Remove-Variable shizukuBotUser, shizukuBotSecure, shizukuBotPassword
```

Bot Passwordの `Allowed pages for editing` には `動画・配信` とだけ入力します。これは `{{DISPLAYTITLE:動画・配信}}` ではありません。複数ページを許可する場合は1行に1ページで指定します。

```powershell
# 認証と対象ページの読み取りだけを確認（編集しない）
python scripts/update_videos_streams.py auth-check
```

「wikiの動画・配信ページを更新して」と依頼すると、まず読み取り専用の確認処理で差分案を作ります。その差分を明示的に承認した後だけ反映し、確認後に別の編集が入っていれば競合として停止します。

```powershell
# ソース取得・YouTube照合・差分案の作成（Wikiは変更しない）
python scripts/update_videos_streams.py check

# 明示的に必要な場合だけショートも含める
python scripts/update_videos_streams.py check --include-shorts

# 表示済みの差分をユーザーが承認した後、出力された確認案を指定して実行
python scripts/update_videos_streams.py apply --plan "outputs/shizuku-wiki/video-streams-r486-xxxxxxxxxxxx.json" --yes
```

確認案は既定で `outputs/shizuku-wiki/` に基準リビジョンと差分ハッシュを含む名前で保存されます。認証情報はこのファイルへ保存されません。

---

## 使い方

```
しずくのwikiの年表を更新して
動画・配信ページを最新にして
メディア露出にこの記事を追加して
```

明示的に「wiki」と言わなくても、しずく・あき先生・年表・配信アーカイブといった話題から起動します。

### 作業の流れ

1. **現在のwikiソースを確認する** — 「動画・配信」はMediaWiki APIから自動取得します。それ以外のページは、取得できない場合にソースの貼り付けを依頼します
2. **追加情報を調べる** — 「動画・配信」はYouTubeの配信と通常動画を照合します。ショートは既定で除外します。それ以外は記事本文、動画リスト、ポスト本文などを使います
3. **差分を受け取る** — 「追記」と「置換」の形で、挿入位置つきで出力されます。この段階ではWikiを編集しません
4. **明示的に承認する** — 承認後、同じ基準リビジョンであることを再確認してからAPIで反映します。競合時は自動停止します

---

## 構成

```
shizuku-wiki/
├── SKILL.md                          振り分け表・共通ルール・トーン5原則
├── LICENSE
├── README.md
├── scripts/
│   └── update_videos_streams.py      動画・配信ページの確認・承認後反映
└── references/
    ├── tone-style-guide.md           文体・語彙・見出しの付け方
    ├── translation-guide.md          日英翻訳の語彙と移行対応表
    ├── page-shizuku.md               しずく（本人ページ）
    ├── page-timeline.md              年表
    ├── page-videos-streams.md        動画・配信
    ├── page-media-coverage.md        メディア露出
    ├── page-fan-activities.md        ファン活動
    ├── page-official-links.md        公式リンク
    └── monitoring-runbook.md         モニタリング運用手順
```

`SKILL.md` は毎回読まれ、`references/` はその作業に必要なものだけが読まれます。

---

## 設計方針

**出力は必ず差分にする。** 長い表を丸ごと再生成させると、既存行の欠落や改変が一定確率で混入し、出力を目視しても気づけません。差分なら変更点だけを検証できます。

**傘スキル1本にする。** ページごとに独立したスキルを作ると、「どのページに書くか」を判断する主体が消えます。同じ出来事が年表とメディア露出の両方に載ることは正常で、粒度を変えて書き分ける必要があります。その判断を持つ場所が必要です。

**毎回必要なルールはSKILL.mdに置く。** `references/` は「読む必要がある」と判断されたときだけ読まれます。日付形式や出典の書式のように例外なく必要なルールを別ファイルに置くと、読まれずに破られます。

**使うたびに更新する。** 作業のたびに振り返り、ガイドに書かれていなかった判断や、指示どおりにやって不都合が出た箇所を洗い出して、更新案を提示します。承認後に反映し、`.skill` を作り直します。詳細は `SKILL.md` §6 にあります。

---

## 貢献

このスキルはしずくWikiの運用ノウハウそのものです。運用ノウハウが1人の手元にしかない状態が、この運用にとって一番の単一障害点です。

改善案・不具合の報告は Issue か、Shizuku LabのDiscordのwiki専用チャンネルへどうぞ。

---

## ライセンス

[MIT License](LICENSE)。改変・再配布・商用利用いずれも自由です。

スキル本体のみが対象で、しずくWikiの記事本文（CC BY-SA）、および「しずく」に関する権利は対象外です。詳細は LICENSE 末尾に記載しています。

---

## 関連リンク

- [しずくWiki](https://shizuku.fandom.com)
- [公式サイト](https://shizuku.ai)
- [YouTube](https://www.youtube.com/@aivtuber_shizuku)
- [X](https://x.com/Shizuku_AItuber)
