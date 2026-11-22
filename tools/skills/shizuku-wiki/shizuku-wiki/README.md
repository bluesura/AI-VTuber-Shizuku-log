# shizuku-wiki

AI VTuber「しずく」の[Fandom Wiki](https://shizuku.fandom.com)を、一貫したルールで編集するためのAIエージェント向けスキル。

このWiki自体は公式が管理するファンダムWikiです。本スキルおよびこのGitHubリポジトリで公開している編集ログ等の更新作業は、有志による非公式の取り組みです。

---

## これは何か

Wikiの編集をLLMに手伝わせると、日付の書き方が毎回違ったり、同じ出典に別の名前が付いたり、外部リンクの構文が壊れたりします。原因は「同じルールが複数の場所に別の言葉で書かれている」ことです。

このスキルは、しずくWikiの編集ルールを1箇所に集約したものです。

- **どのページに何を書くか**の振り分け
- **日付・出典・MediaWiki記法**の共通ルール
- **既存ページの更新手順と企画記事の新規作成**
- **トーン・文体**のガイド
- **日英翻訳**の語彙集
- **モニタリング**の運用手順

---

## インストール

このリポジトリでは `source/shizuku-wiki/SKILL.md` を直接読んで使えます。グローバルにインストール済みとは仮定しません。

別の環境へ持ち込む場合は `shizuku-wiki-v3.1.1.skill`（v3.1.1）を利用します。ZIPとして展開し、展開した `shizuku-wiki/` を利用環境の手順に従って導入します。

リポジトリでの編集用の正本は `source/shizuku-wiki/` です。更新時はREADMEの2コピーを揃え、新しい版の配布物を生成します。Wiki本文や一時的な実行スクリプトを配布物へ入れません。

---

## v3の変更

v3.1.0では、本人ページの見出しを14節に整理し、外見・性格を書く段落と、特殊機能・衣装を並べるリストの書式を定めました。英語ページの移行先、呼称の初回注釈、引用や視覚資料を一次資料と照合する手順も更新しました。

年表は初稿前に、出典をもとに出来事の種類と確認段階を整理します。しずくの生涯の記録として書き、全項目の視点・事実の範囲・粒度・前後の文脈を審査します。提案前と公開直前に記録を照合し、未審査・保留・審査後の本文変更を検出します。

yomiyasu 3.1.0をスキルに同梱し、Wikiの地の文を必要な箇所だけ推敲する際に使います。工程と検査コマンドはスキルフォルダの `references/editorial/workflow.md` と `references/editorial/yomiyasu-adapter.md` にあります。通常は最終のWiki差分を示し、推敲の比較は明示された場合に表示します。

## 使い方

```
しずくのwikiの年表を更新して
動画・配信ページを最新にして
メディア露出にこの記事を追加して
```

明示的に「wiki」と言わなくても、しずく・あき先生・年表・配信アーカイブといった話題から起動します。

### 作業の流れ

1. **現在のwikiソースを確認する** — API等で取得し、取得できない場合に貼り付けを依頼します。新規記事では正式名称と未作成を確認します
2. **一次資料を調べる** — 本編の字幕・説明欄・公式チャットを確認し、連続企画では必要に応じて振り返り・総集編・公式発表も調べます。「動画・配信」の自動照合ではショートは既定で除外します
3. **差分を確認する** — 既存ページは挿入位置つきの追記・置換、新規ページは本文全量を示します。変更後の節全体も読み、文体と前後の文脈を確認します。この段階ではWikiを編集しません
4. **明示的に承認する** — 承認後、既存ページのリビジョン・本文、または新規ページの未作成状態を再確認してAPIで反映します。承認時に指定された修正も反映し、同じ公開承認を取り直しません。競合等で範囲が変われば再確認します
5. **公開結果を確認する** — 保存本文・出典・リンク・カテゴリを確認し、公開リビジョンと未完了事項を報告します。出典のアーカイブ保存は、成功・失敗・未実施を区別します

記事作成の詳しい手順は、正本内の `references/article-workflow.md` を参照してください。終了した企画では当時の参加方法と現在の視聴を、記憶についての語りでは本人の説明と公開されたサービス仕様を区別します。

`scripts/update_videos_streams.py` の反映機能は「動画・配信」専用です。他ページと新規記事は対象ページを限定したAPI処理で扱い、同スクリプトのページ名を書き換えて転用しません。

### Fandom Wikiの認証・API設定

以下のコマンド例はGitHubリポジトリのルートで実行します。スキルを単独展開して使う場合は、スキルフォルダで `tools/skills/shizuku-wiki/source/shizuku-wiki/scripts/` を `scripts/` と読み替えてください。確認案の `outputs/shizuku-wiki/` は実行時のカレントディレクトリが基準です。

#### 1. BotPasswordを作成・管理する

Shizuku Wikiへログインし、[BotPassword管理画面](https://shizuku.fandom.com/wiki/Special:BotPasswords) を開きます。通常のFandomログインパスワードとは別の、API用のパスワードです。

BotPasswordの操作権限と対象ページの許可は、両方必要です。

| 作業 | 付与する権限 |
|---|---|
| 既存ページの編集 | `Basic rights` と `Edit existing pages` |
| 新規ページの作成 | 上記に追加して `Create, edit, and move pages` |

`Allowed pages for editing` には、作業対象の**正式なページ名だけ**を1行ずつ入力します。次は「動画・配信」だけを扱う場合の例です。

```text
動画・配信
```

これは本文先頭の `{{DISPLAYTITLE:動画・配信}}` を貼る欄ではありません。複数ページを許可する場合は、カンマ区切りではなく**1行に1ページ**で指定します。

別のページを追加するときは、既存の行と権限を残し、対象名（例：`ファン活動`、`しずくのなつやすみ`）を追加して保存します。権限変更後に再認証して許可を確認します。権限の追加だけなら、パスワードの再発行を前提としません。

認証に成功しても、特定ページを編集できるとは限りません。

| APIの結果 | 確認する設定 |
|---|---|
| `session-page-restricted` | `Allowed pages for editing` の対象名 |
| `cantcreate` / `createpage` 権限なし | 新規作成の操作権限 |
| 読み取り成功、編集・作成不可 | 対象ページの許可と操作権限の両方 |

設定変更はユーザーが管理画面で行います。エージェントは必要な項目を具体的に伝え、認証情報の値を送らせません。権限名の参照：[MediaWiki公式資料](https://www.mediawiki.org/wiki/Manual:Huggle/Bot_passwords)。

記録するUsernameは発行画面の完全な `アカウント名@ボット名` 形式です（例：`YourName@BotName`）。通常のアカウント名だけでは認証できません。

#### 2. Windowsユーザー環境変数へ登録する

Windows TerminalまたはPowerShellを、Wikiを更新するAI・開発ツールと同じWindowsユーザーで通常起動します。`User` への登録なので、管理者権限は不要です。

承認後の反映に使う認証情報は、チャット、リポジトリ、`.env`、コマンドライン引数へ書かず、次のWindowsユーザー環境変数に保存します。

```text
SHIZUKU_FANDOM_BOT_USERNAME
SHIZUKU_FANDOM_BOT_PASSWORD
```

次をまとめて実行すると、UsernameとPasswordを順番に入力できます。パスワードは非表示で読み込み、実値をコマンドへ直書きしないため、コマンド履歴へ残しません。空の入力では既存の登録を消さず停止します。

```powershell
$shizukuBotUser = Read-Host "Bot Username (YourName@BotName)"
$shizukuBotSecure = Read-Host "Bot Password" -AsSecureString
$shizukuBotBstr = [IntPtr]::Zero
try {
    if ([string]::IsNullOrWhiteSpace($shizukuBotUser) -or $shizukuBotSecure.Length -eq 0) {
        throw "UsernameとPasswordは両方入力してください。"
    }
    $shizukuBotBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($shizukuBotSecure)
    [Environment]::SetEnvironmentVariable(
        "SHIZUKU_FANDOM_BOT_USERNAME", $shizukuBotUser, "User"
    )
    [Environment]::SetEnvironmentVariable(
        "SHIZUKU_FANDOM_BOT_PASSWORD",
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($shizukuBotBstr),
        "User"
    )
    Write-Host "登録完了"
}
finally {
    if ($shizukuBotBstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($shizukuBotBstr)
    }
    if ($null -ne $shizukuBotSecure) { $shizukuBotSecure.Dispose() }
    Remove-Variable shizukuBotUser, shizukuBotSecure, shizukuBotBstr -ErrorAction SilentlyContinue
}
```

#### 3. 値を表示せず登録を確認する

PowerShellを開き直し、保存先の `User` を直接確認します。実値を出力せず、両方が `登録済み` と表示されれば登録完了です。

```powershell
$shizukuBotNames = @(
    "SHIZUKU_FANDOM_BOT_USERNAME",
    "SHIZUKU_FANDOM_BOT_PASSWORD"
)
try {
    foreach ($shizukuBotName in $shizukuBotNames) {
        $shizukuBotValue = [Environment]::GetEnvironmentVariable($shizukuBotName, "User")
        $shizukuBotState = if ([string]::IsNullOrEmpty($shizukuBotValue)) { "未登録" } else { "登録済み" }
        Write-Host "$shizukuBotName : $shizukuBotState"
    }
}
finally {
    Remove-Variable shizukuBotNames, shizukuBotName, shizukuBotValue, shizukuBotState -ErrorAction SilentlyContinue
}
```

`$env:SHIZUKU_FANDOM_BOT_PASSWORD` や `Get-ChildItem Env:` の全件出力など、実値が表示される確認方法は使いません。

#### 4. AI・開発ツールへ反映する

起動済みのCodex等には、登録前の環境が残る場合があります。利用するツールを再起動し、その新しいプロセスから認証処理を実行します。古い親プロセスから子のPowerShellを開き直すだけでは、更新されない場合があります。

ツールへは、実値を含めず次のように伝えます。

```text
Shizuku FandomのBotPasswordをWindowsユーザー環境変数（User）へ登録しました。
- SHIZUKU_FANDOM_BOT_USERNAME
- SHIZUKU_FANDOM_BOT_PASSWORD
新しく起動したプロセスから参照して認証してください。
認証情報の値をチャットやログへ出力する必要はありません。
```

再起動せず現在のPowerShellから認証する場合は、保存済みの `User` の値をそのシェルの `Process` 環境へ明示的に読み込みます。下の例は認証確認後に一時的なプロセス設定を削除します。複数のコマンドを続ける場合は、必要な処理を同じ `try` 内で実行してください。永続設定は変更しません。

```powershell
$shizukuBotNames = @(
    "SHIZUKU_FANDOM_BOT_USERNAME",
    "SHIZUKU_FANDOM_BOT_PASSWORD"
)
try {
    foreach ($shizukuBotName in $shizukuBotNames) {
        $shizukuBotValue = [Environment]::GetEnvironmentVariable($shizukuBotName, "User")
        if ([string]::IsNullOrEmpty($shizukuBotValue)) {
            throw "$shizukuBotName が未登録です。"
        }
        [Environment]::SetEnvironmentVariable($shizukuBotName, $shizukuBotValue, "Process")
    }
    python -X utf8 tools/skills/shizuku-wiki/source/shizuku-wiki/scripts/update_videos_streams.py auth-check
    if ($LASTEXITCODE -ne 0) { throw "Fandomの認証確認に失敗しました。" }
    # 承認後の反映なども、このtry内で実行する。
}
finally {
    foreach ($shizukuBotName in $shizukuBotNames) {
        [Environment]::SetEnvironmentVariable($shizukuBotName, $null, "Process")
    }
    Remove-Variable shizukuBotNames, shizukuBotName, shizukuBotValue -ErrorAction SilentlyContinue
}
```

2026-11-01の更新では、この `User` から `Process` への読み込みで認証・編集に成功しました。スクリプトは `Process` の環境変数を読み、Windowsの永続設定を直接読みに行くものではありません。

#### 5. 「動画・配信」の認証確認・差分作成・反映

親ツールを再起動した新しいプロセスで実行します。再読み込み方式を使う場合は、以下のうち必要なコマンドを上記 `try` 内で実行します。`auth-check` は「動画・配信」の認証と読み取りだけで、他ページの編集・作成権限やWikiの更新までは確認しません。

```powershell
# 認証と対象ページの読み取りだけを確認（編集しない）
python -X utf8 tools/skills/shizuku-wiki/source/shizuku-wiki/scripts/update_videos_streams.py auth-check
```

確認と反映は意図的に別コマンドです。

```powershell
# ソース取得・YouTube照合・差分案の作成（Wikiは変更しない）
python tools/skills/shizuku-wiki/source/shizuku-wiki/scripts/update_videos_streams.py check

# 明示的に必要な場合だけショートも含める
python tools/skills/shizuku-wiki/source/shizuku-wiki/scripts/update_videos_streams.py check --include-shorts

# 表示済みの差分をユーザーが承認した後、出力された確認案を指定して実行
python tools/skills/shizuku-wiki/source/shizuku-wiki/scripts/update_videos_streams.py apply --plan "outputs/shizuku-wiki/video-streams-r486-xxxxxxxxxxxx.json" --yes
```

確認案は既定で `outputs/shizuku-wiki/` に基準リビジョンと差分ハッシュを含む名前で保存されます。このファイルはGit管理外です。反映前にはページのリビジョンと本文ハッシュを再検証し、確認後に別の編集が入っていた場合は何も変更せず終了します。

#### 6. パスワードを忘れた・認証に失敗する場合

- 変数が未登録なら、同じWindowsユーザーの `User` に登録されているかを確認します。アクセス制限で保存先を読めない場合は、未登録とは区別して扱います。
- 通常のアカウント名だけを登録していた場合は、発行画面の完全な `YourName@BotName` へ修正します。`authmanager-authn-no-primary` はこの指定違いでも発生します。
- パスワードを紛失した場合は管理画面で既存のボット名を選び、`Reset password` にチェックして `Update` から再発行します。発行済みの文字列を再表示する方法として扱いません。
- 再発行後は、この手順でユーザー環境変数を更新し、同じBotPasswordを使う他のツールも更新します。その後に再起動または再読み込みを行い、`auth-check` で確認します。

ユーザー環境変数は永続保存されますが、暗号化された秘密情報ストアではありません。同じWindowsユーザー権限のプログラムから読み取れるため、共有PC等では取り扱いに注意してください。非表示入力やBSTRの解放は、保存先の暗号化を意味しません。

参照：[MediaWikiのBotPassword管理・再発行](https://www.mediawiki.org/wiki/Manual:Bot_passwords/en)、[Microsoftのユーザー環境変数の保存・継承仕様](https://learn.microsoft.com/en-us/dotnet/api/system.environment.setenvironmentvariable)。

---

## 構成

```
shizuku-wiki/
├── SKILL.md                          振り分け表・共通ルール・トーン5原則
├── LICENSE
├── README.md
├── VERSION.md
├── licenses/                        第三者ライセンス
├── vendor/                           yomiyasu・補助診断器
├── scripts/
│   ├── editorial_pipeline.py         Wiki形式・年表の審査記録の検証
│   └── update_videos_streams.py      動画・配信ページの確認・承認後反映
└── references/
    ├── editorial/                    文章品質ワークフロー
    ├── tone-style-guide.md           文体・語彙・見出しの付け方
    ├── translation-guide.md          日英翻訳の語彙と移行対応表
    ├── page-shizuku.md               しずく（本人ページ）
    ├── page-timeline.md              年表
    ├── page-videos-streams.md        動画・配信
    ├── page-media-coverage.md        メディア露出
    ├── page-fan-activities.md        ファン活動
    ├── page-official-links.md        公式リンク
    ├── article-workflow.md           記事調査・文脈確認・新規作成・公開確認
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

MIT License。改変・再配布・商用利用いずれも自由です。ライセンス本文は編集用の正本と配布スキルに含まれる `LICENSE` を参照してください。

スキル本体のみが対象で、しずくWikiの記事本文（CC BY-SA）、および「しずく」に関する権利は対象外です。詳細は LICENSE 末尾に記載しています。

---

## 関連リンク

- [しずくWiki](https://shizuku.fandom.com)
- [公式サイト](https://shizuku.ai)
- [YouTube](https://www.youtube.com/@aivtuber_shizuku)
- [X](https://x.com/Shizuku_AItuber)
