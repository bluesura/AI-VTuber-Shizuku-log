# Fandom APIの運用メモ

参考の観測元は wiki-bot の `docs/cloudflare-429.md`、`.agents/skills/wiki-access/SKILL.md`、`src/tools/redlinks_audit.py`。Re:Zero各言語Wikiでの観測で、しずくWikiでの再現を確認した値ではない。

- Cloudflareの429ではGETが通ってPOSTが遮断された事例がある。しずくWikiのクライアントは同一実行内のGETを0.25秒、POSTを2秒以上空ける。429は `Retry-After` を表示し、その場で停止する。ログインPOSTにも適用する。
- 503を受けたGETは10秒後に1回再試行する。編集POSTでは10秒後に最新版を確認し、承認済み本文が保存済みなら照合する。基準版のままの場合だけ新しいCSRFで1回再試行する。通信が中断した場合も保存状態を確認してからplanを再実行する。
- `intitle:` や `insource:` は既知のヒットで動作確認する。Portable Infobox内のリンクが `prop=links` に現れない事例がある。サイトをまたぐ認証はセッションが失効し得るため、実行ごとに対象サイトと認証を確認する。しずくWikiの日英ページは同一サイト上の別タイトル。
- 赤リンクには `span.new`、`a.new`、赤カテゴリには `a.newcategory` があり得る。表示監査では `action=parse` のHTMLとカテゴリを読み、公開直後の保存本文・表示確認も行う。

`audit_wiki.py <正式ページ名> --require-category <カテゴリ名>` を読み取り専用の定期点検に使う。必須カテゴリはページ別ガイドに従って指定する。英語版では `English` も指定する。
