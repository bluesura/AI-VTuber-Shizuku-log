# X (x.com) ログ定期収集・統合ワークフロー手順書

対象リポジトリ: `AI-VTuber-Shizuku-log`

対象アカウントは `@Shizuku_AItuber`、`@cumulo_autumn`、`@ShizukuResearch`。

対象スキーマ: 20列 X TSV（UTF-8 / BOMなし / LF / `date_utc` 降順）

## 0. このワークフローの基本設計（なぜ 2 段階に分けるのか）

以前の DOM 直接スクレイピング方式では、以下の 3 つのデータ欠損が構造的に発生していました。

1. **仮想スクロールによる取りこぼし**: X のタイムラインは `div[data-testid="cellInnerDiv"]` を絶対配置で再利用するため、最下部までスクロールした後に `querySelectorAll` を実行すると、画面外に消えた上部のツイートが DOM から消滅して拾えません。

2. **絵文字の欠落**: X の Web 表示では標準絵文字が `<img>` タグへ置換されるため、DOM のテキスト抽出では推しマークなどの絵文字が抜け落ちます。

3. **URL・引用元の途切れ**: 短縮 URL（`t.co`）や長文の引用ツイートが DOM 上で省略・打ち切り表示されることがあります。

これを根本解決するため、本ワークフローでは役割を明確に分離します。

* **ブラウザ側（自動スクロール＋ID回収）**: 検索結果の最上部から最下部まで自動スクロールしながら **`post_id` だけ** をリアルタイムに漏れなく回収し、末尾到達で自動終了してクリップボードへコピー（または TXT 保存）する。

* **ローカル側（AI / スクリプト実行）**: 回収した `post_id` を **FxTwitter API** に通し、全文・標準絵文字・展開済み URL・引用・返信先・反応数を確定取得して 20 列 TSV に統合する。

## Step 1: X 検索クエリの作成と画面準備（人間操作）

1. X にログインした状態で検索バーを開きます。複数アカウントをまとめて検索する場合は `OR` でつなぎます。

```text
(from:Shizuku_AItuber OR from:cumulo_autumn OR from:ShizukuResearch) -filter:retweets since:2026-06-01 until:2026-07-01
```

アカウント別に収集する場合は以下を使用します。

```text
from:Shizuku_AItuber -filter:retweets since:2026-06-01 until:2026-07-01
from:cumulo_autumn -filter:retweets since:2026-06-01 until:2026-07-01
from:ShizukuResearch -filter:retweets since:2026-06-01 until:2026-07-01
```

### クエリ設定の注意点

* **`-filter:retweets` を必ず付ける**: 本人の単純リポスト（他人の投稿の RT）が混入するのを防ぎます。引用リポスト（QT）は検索結果に残ります。

* **「最新（Latest）」タブに切り替える**: 検索直後は「話題（Top）」タブが開くため、必ず検索結果上部の **「最新」タブ**（URL に `&f=live` が付く状態）に切り替えてから収集を開始してください。

* **UTC 時差の 1 日マージン**: X 検索の `since:` / `until:` は UTC 基準で判定されます。JST の月跨ぎを取りこぼさないよう、前回収集日の **1 日前** を `since:` に指定してください（重複した ID は Step 3 で自動除外されます）。

## Step 2: 自動スクロール対応 ID 回収スクリプトの実行（人間操作）

> **重要**: 検索結果を開いて **最上部にいる状態** で実行してください（実行すると自動で最下部までスクロールし、末尾到達で自動停止します）。

検索画面の `article[data-testid="tweet"]` 内には投稿、引用元、`/analytics` などへのリンクが混在します。以下のスクリプトは自動スクロールと `MutationObserver` を使い、対象アカウントの `/<ハンドル>/status/<ID>` に一致し、`<time>` 要素を含むリンクから投稿 ID を収集します。

### 工夫しているポイント

* **取りこぼし防止の 85% スクロール**: `window.innerHeight * 0.85` ずつスクロールし、前後の画面を 15% 重ねることで境界部分のツイート抜けを防ぎます。

* **読み込み待ちリトライ**: ネットワーク待ちで新規件数が増えない回数が `MAX_RETRIES`（8 回 × 500ms ＝ 約 4 秒）連続した時点で末尾到達と判定して自動終了します。

* **クリップボード＆ファイル出力**: 完了時に自動でクリップボードへのコピーを試行し、`window.shizukuIdsText` にも格納します。ブラウザ制約で自動コピーが弾かれた場合も、右下の HUD ボタン（**「IDをコピー」** / **「TXT保存」**）または Console の `copy(window.shizukuIdsText)` で即座に取得できます。

### 方法 A: DevTools コンソールから実行する（推奨）

ブラウザで `F12`（または `Cmd+Option+I`）→ **Console** タブを開き、以下を貼り付けて `Enter` を押します。

```javascript
(() => {
  if (window.__shizukuCollectorCleanup) {
    window.__shizukuCollectorCleanup();
  }

  const TARGET_HANDLES = ['Shizuku_AItuber', 'cumulo_autumn', 'ShizukuResearch'];
  const STATUS_RE = new RegExp(`^\\/(?:${TARGET_HANDLES.join('|')})\\/status\\/(\\d+)$`, 'i');
  const INTERVAL_MS = 500;
  const MAX_RETRIES = 8;

  const collected = new Map(); // post_id -> date_utc
  let lastCount = -1;
  let noNewCount = 0;
  let timer = null;
  let isPaused = false;
  let isFinished = false;

  function scanVisibleTweets() {
    let added = 0;
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    for (const article of articles) {
      const links = article.querySelectorAll('a[href*="/status/"]');
      for (const link of links) {
        const href = link.getAttribute('href') || '';
        const match = href.match(STATUS_RE);
        if (!match) continue;

        // 引用ツイート等の誤混入を防ぐため、<time datetime="..."> を伴う投稿パーマリンクのみ採用
        const timeEl = link.querySelector('time[datetime]');
        if (!timeEl) continue;

        const postId = match[1];
        const dateUtc = timeEl.getAttribute('datetime') || '';
        if (!collected.has(postId)) {
          collected.set(postId, dateUtc);
          added++;
        }
      }
    }
    if (added > 0) updateHud();
    return added;
  }

  function getSortedIdsText() {
    return Array.from(collected.entries())
      .sort((a, b) => (b[1] || '').localeCompare(a[1] || '') || b[0].localeCompare(a[0]))
      .map(([id]) => id)
      .join('\n');
  }

  // 右下に操作用フローティング HUD を表示
  const hud = document.createElement('div');
  hud.id = 'shizuku-id-collector-hud';
  hud.style.cssText = [
    'position:fixed', 'right:16px', 'bottom:16px', 'z-index:999999',
    'background:#111827', 'color:#f9fafb', 'padding:12px 14px',
    'border-radius:10px', 'font:13px/1.4 system-ui,sans-serif',
    'box-shadow:0 8px 24px rgba(0,0,0,0.35)', 'min-width:260px',
    'border:1px solid #374151'
  ].join(';');

  const statusLabel = document.createElement('div');
  statusLabel.style.cssText = 'font-weight:700;margin-bottom:4px;';

  const subLabel = document.createElement('div');
  subLabel.style.cssText = 'font-size:11px;color:#9ca3af;margin-bottom:8px;';

  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;';

  function makeBtn(text, bg, onClick) {
    const b = document.createElement('button');
    b.textContent = text;
    b.style.cssText = `background:${bg};color:#fff;border:none;border-radius:6px;padding:6px 10px;cursor:pointer;font-size:12px;font-weight:600;`;
    b.onclick = onClick;
    return b;
  }

  function updateHud(extraText = '') {
    const stateText = isFinished
      ? '✅ 収集完了'
      : isPaused
        ? '⏸ 一時停止中'
        : '🔍 自動スクロール中';
    statusLabel.textContent = `${stateText}: ${collected.size} 件`;
    subLabel.textContent = extraText || (
      isFinished
        ? '下のボタンからコピーまたはTXT保存できます'
        : `末尾判定: ${noNewCount}/${MAX_RETRIES}`
    );
  }

  const pauseBtn = makeBtn('一時停止', '#d97706', () => {
    if (isFinished) return;
    isPaused = !isPaused;
    pauseBtn.textContent = isPaused ? '再開' : '一時停止';
    updateHud();
  });

  const copyBtn = makeBtn('IDをコピー', '#2563eb', async () => {
    scanVisibleTweets();
    const text = getSortedIdsText();
    window.shizukuIdsText = text;
    try {
      await navigator.clipboard.writeText(text);
      copyBtn.textContent = `コピー完了 (${collected.size})`;
    } catch {
      window.prompt('クリップボードへの自動コピーに失敗しました。以下をコピーしてください:', text);
    }
    setTimeout(() => { copyBtn.textContent = 'IDをコピー'; }, 2000);
  });

  const dlBtn = makeBtn('TXT保存', '#059669', () => {
    scanVisibleTweets();
    const text = getSortedIdsText() + '\n';
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const today = new Date().toISOString().slice(0, 10);
    a.href = url;
    a.download = `shizuku_post_ids_${today}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  });

  const stopBtn = makeBtn('終了', '#4b5563', () => {
    cleanup();
  });

  btnRow.append(pauseBtn, copyBtn, dlBtn, stopBtn);
  hud.append(statusLabel, subLabel, btnRow);
  document.body.appendChild(hud);

  const observer = new MutationObserver(() => scanVisibleTweets());
  observer.observe(document.body, { childList: true, subtree: true });

  async function finish() {
    if (isFinished) return;
    isFinished = true;
    clearInterval(timer);
    timer = null;
    scanVisibleTweets();

    const text = getSortedIdsText();
    window.shizukuIdsText = text;

    console.log(`\n✅ 収集完了: ${collected.size} 件 (${TARGET_HANDLES.map(h => '@' + h).join(', ')})`);
    if (!collected.size) {
      console.log('データなし');
      updateHud('対象投稿が見つかりませんでした');
      return;
    }

    let copied = false;
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch {
      // 画面非フォーカス時などはブラウザ仕様で失敗するため HUD ボタンで案内
    }

    console.log('--- 収集した post_id 一覧 ---');
    console.log(text);
    console.log('--- ここまで ---');
    console.log('📋 手動コピー: copy(window.shizukuIdsText)');
    updateHud(copied ? 'クリップボードに自動コピーしました' : '「IDをコピー」または「TXT保存」を押してください');
  }

  function cleanup() {
    if (timer) clearInterval(timer);
    observer.disconnect();
    hud.remove();
    delete window.__shizukuCollectorCleanup;
  }

  window.__shizukuCollectorCleanup = cleanup;
  window.__shizukuCollectedMap = collected;

  console.log(`🔍 自動スクロール収集開始... (${TARGET_HANDLES.map(h => '@' + h).join(', ')})`);
  console.log('ページ末尾に到達すると自動終了します。');
  scanVisibleTweets();
  updateHud();

  timer = setInterval(() => {
    if (isPaused || isFinished) return;
    scanVisibleTweets();
    const count = collected.size;
    if (count === lastCount) {
      noNewCount++;
      console.log(`新規データなし (${noNewCount}/${MAX_RETRIES})`);
    } else {
      noNewCount = 0;
      console.log(`✔ ${count} 件収集済み`);
    }
    lastCount = count;
    updateHud();

    if (noNewCount >= MAX_RETRIES) {
      finish();
      return;
    }
    window.scrollBy(0, Math.floor(window.innerHeight * 0.85));
  }, INTERVAL_MS);
})();
```

### 方法 B: ブックマークレットとして登録する

ブラウザのブックマークバーに新規ブックマークを追加し、URL 欄に以下をそのまま貼り付けます（検索画面の最上部でクリックするだけで自動スクロール＋収集が開始されます）。

```text
javascript:(()=>{if(window.__shizukuCollectorCleanup)window.__shizukuCollectorCleanup();const R=/^\/(?:Shizuku_AItuber|cumulo_autumn|ShizukuResearch)\/status\/(\d+)$/i,I=500,X=8,M=new Map();let L=-1,N=0,tm=null,P=false,F=false;function S(){let a=0;for(const ar of document.querySelectorAll('article[data-testid="tweet"]')){for(const l of ar.querySelectorAll('a[href*="/status/"]')){const m=(l.getAttribute('href')||'').match(R);if(!m)continue;const t=l.querySelector('time[datetime]');if(!t)continue;if(!M.has(m[1])){M.set(m[1],t.getAttribute('datetime')||'');a++;}}}if(a>0)U();return a;}const G=()=>Array.from(M.entries()).sort((a,b)=>(b[1]||'').localeCompare(a[1]||'')||b[0].localeCompare(a[0])).map(([i])=>i).join('\n');const h=document.createElement('div');h.style.cssText='position:fixed;right:16px;bottom:16px;z-index:999999;background:#111827;color:#f9fafb;padding:12px 14px;border-radius:10px;font:13px/1.4 system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.35);min-width:260px;border:1px solid #374151';const sl=document.createElement('div');sl.style.cssText='font-weight:700;margin-bottom:4px';const sb=document.createElement('div');sb.style.cssText='font-size:11px;color:#9ca3af;margin-bottom:8px';const r=document.createElement('div');r.style.cssText='display:flex;gap:6px;flex-wrap:wrap';const B=(t,g,f)=>{const b=document.createElement('button');b.textContent=t;b.style.cssText=`background:${g};color:#fff;border:none;border-radius:6px;padding:6px 10px;cursor:pointer;font-size:12px;font-weight:600`;b.onclick=f;return b;};function U(e=''){sl.textContent=`${F?'✅ 収集完了':P?'⏸ 一時停止中':'🔍 自動スクロール中'}: ${M.size} 件`;sb.textContent=e||(F?'下のボタンからコピーまたはTXT保存できます':`末尾判定: ${N}/${X}`);}const pb=B('一時停止','#d97706',()=>{if(F)return;P=!P;pb.textContent=P?'再開':'一時停止';U();});const cp=B('IDをコピー','#2563eb',async()=>{S();const t=G();window.shizukuIdsText=t;try{await navigator.clipboard.writeText(t);cp.textContent=`完了(${M.size})`;}catch{prompt('コピー:',t);}setTimeout(()=>cp.textContent='IDをコピー',2e3);});const dl=B('TXT保存','#059669',()=>{S();const u=URL.createObjectURL(new Blob([G()+'\n'],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download=`shizuku_post_ids_${new Date().toISOString().slice(0,10)}.txt`;a.click();URL.revokeObjectURL(u);});const st=B('終了','#4b5563',()=>C());r.append(pb,cp,dl,st);h.append(sl,sb,r);document.body.appendChild(h);const o=new MutationObserver(S);o.observe(document.body,{childList:true,subtree:true});async function E(){if(F)return;F=true;clearInterval(tm);tm=null;S();const t=G();window.shizukuIdsText=t;let ok=false;try{await navigator.clipboard.writeText(t);ok=true;}catch{}U(ok?'クリップボードに自動コピーしました':'「IDをコピー」または「TXT保存」を押してください');}function C(){if(tm)clearInterval(tm);o.disconnect();h.remove();delete window.__shizukuCollectorCleanup;}window.__shizukuCollectorCleanup=C;window.__shizukuCollectedMap=M;S();U();tm=setInterval(()=>{if(P||F)return;S();const c=M.size;N=(c===L)?N+1:0;L=c;U();if(N>=X){E();return;}window.scrollBy(0,Math.floor(window.innerHeight*.85));},I);})();
```

### 実行から保存までの手順

1. 検索結果（「最新」タブ）の最上部でコンソール版またはブックマークレットを実行する。

2. 画面が自動で下へスクロールし、右下の HUD に `🔍 自動スクロール中: ... 件` がカウントアップされるのを確認する（途中で止めたい場合は **「一時停止」** を押せます）。

3. 末尾に到達して `✅ 収集完了` になったら、自動コピー結果を確認するか **「TXT保存」**（`shizuku_post_ids_YYYY-MM-DD.txt`）または **「IDをコピー」** をクリックして ID リストを確定する。

## Step 3: 差分抽出と FxTwitter による 20 列データ生成（AI / スクリプト実行）

保存した `shizuku_post_ids_YYYY-MM-DD.txt` をリポジトリ作業フォルダ（例: `outputs/x_intake/`）に置き、以下の処理を実行します。

### 3.1 既存ログとの重複排除

* `logs/twitter(x)/` 以下の全アカウントを再帰的に検索し、`.txt` / `.tsv` に収録済みの `post_id` を除きます。

### 3.2 FxTwitter API による確定データ取得

新規 `post_id` ごとに FxTwitter の `status` API を呼び出し、以下を取得・整形します。

* **基本ルール**:

  * **ページ連結は使用しない**（タイムライン連結時の終了判定バグを回避するため、必ず 1 投稿単位の `status` 呼び出しを行う）。

  * リクエストごとに HTTP ステータスと API 応答コードを確認する。

  * `status` の投稿 ID と投稿者ハンドルを照合する。確認できた対象アカウントのハンドルを `author` と保存先フォルダに使う。

* **テキスト・URL・メディア**:

  * JSON の `text` と `raw_text.facets` を参照し、標準絵文字を保持したまま `t.co` を展開後の完全 URL に復元する。

  * 展開済み URL は `extracted_urls`、添付画像・動画 URL は `media_urls` に格納する。

* **引用（`QUOTE`）**:

  * `quote_post_id`, `quote_author`, `quote_text` を格納する。一般ユーザーの引用元は既存ルールに従い匿名化または最小保持とする。

* **返信先（`REPLY`）の補完と匿名化**:

  * `status` で親投稿情報が得られない場合は `thread` → `conversation` の順で補完する。

  * `reply_to_author`（および `quote_author`）はホワイトリスト対象のみ実ハンドルを保持し、一般視聴者は共通ソルトで `User_<8桁hash>` に匿名化する。

  * **ホワイトリスト対象（実ハンドル保持）**:
    * `Shizuku_AItuber`（しずく本体）
    * `ShizukuResearch`（しずくリサーチ公式アカウント）
    * `cumulo_autumn` / `Aki` / `aki5503`（開発者・あき先生）
    * その他 `tools/scripts/anon_whitelist.txt` に登録された公式・コラボ相手アカウント

  * **親投稿の本文は保存しない**（追跡は `reply_to_post_id` から行う）。

  * 削除・凍結等で親 ID が取得できない場合のみ `quality_flags` に `missing_parent` を記録する。

* **メタデータ列**:

  * `snapshot_date`・`metrics_date`: 取得日（`YYYY-MM-DD`）

  * `source_method`: `fxtwitter`

### 20 列 TSV スキーマ定義（厳守）

| 順 | 列名 | 説明 |
| ----- | ----- | ----- |
| 1 | `post_id` | 投稿 ID（数値文字列） |
| 2 | `date_utc` | UTC 投稿日時（ISO 8601） |
| 3 | `author` | 投稿者ハンドル（`Shizuku_AItuber` / `cumulo_autumn` / `ShizukuResearch`） |
| 4 | `type` | `POST` / `REPLY` / `QUOTE` / `REPLY_QUOTE` 等 |
| 5 | `text` | 本文（絵文字保持・タブ/改行正規化済み） |
| 6 | `extracted_urls` | `facets` 等から復元した展開済み URL |
| 7 | `quote_post_id` | 引用元投稿 ID |
| 8 | `quote_author` | 引用元投稿者 |
| 9 | `quote_text` | 引用元本文 |
| 10 | `reply_to_post_id` | 返信先投稿 ID |
| 11 | `reply_to_author` | 返信先投稿者（ホワイトリスト以外は `User_XXXXXXXX`） |
| 12 | `media_urls` | 画像・動画メディア URL |
| 13 | `likes` | いいね数 |
| 14 | `reposts` | リポスト数 |
| 15 | `replies` | 返信数 |
| 16 | `views` | 表示回数 |
| 17 | `snapshot_date` | ログ取得日（`YYYY-MM-DD`） |
| 18 | `metrics_date` | 反応数取得日（`YYYY-MM-DD`） |
| 19 | `source_method` | 取得経路（新規収集は `fxtwitter`） |
| 20 | `quality_flags` | `missing_parent` 等の品質フラグ |

## Step 4: TSV マージ・パイプライン正規化・検証（AI / スクリプト実行）

1. **対象 TSV ファイルへの統合**:

   * `logs/twitter(x)/<ハンドル>/<対象期間>.txt` に追加する。フォルダ名は `@` を除いたハンドルとし、年・月の区切りは JST で判定する。例として、しずく本体の2026年6〜12月分は `logs/twitter(x)/Shizuku_AItuber/202606-12.txt`、開発・運営の投稿を年別に保存する場合は `cumulo_autumn/2026.txt` や `ShizukuResearch/2026.txt` を使う。

   * ファイルの全行で `author` とフォルダ名が一致することを確認し、`post_id` で重複排除して `date_utc` 降順でソートする。

   * 書き出し前に **20 列一致・UTF-8（BOM なし）・改行コード LF** をプログラムで検証する。

2. **取り込み用フォルダへの同期**:

   * 更新した TSV を `tools/shizuku-pipeline/data/raw/x/<ハンドル>/` の同名ファイルへ同期し、バイト単位で一致することを確認する。下記の S0 コマンドで X ログだけを同期できる。

3. **正規化・診断パイプラインの実行**:

```bash
python tools/shizuku-pipeline/scripts/s0_intake.py --src 'logs/twitter(x)'
python tools/shizuku-pipeline/scripts/s1_normalize.py --x
python tools/shizuku-pipeline/scripts/doctor.py
```

4. **合格基準**:

   * `doctor.py` の結果が **`ERROR 0`** であること。

   * 新規追加行に起因する `WARN` が **0 件** であること。

   * 既存テスト（`tools/shizuku-pipeline` のテストスイート）および `git diff --check` がすべて通過すること。

## 付録: AI エージェント（Codex 等）へ作業を依頼するときの指示テンプレート

ID リスト（`shizuku_post_ids_YYYY-MM-DD.txt`）を保存したあと、AI エージェントへ以下のように指示すると Step 3〜4 を一貫して実行できます。

```text
tools/workflows/x_collection_workflow.md の Step 3〜4 に従って、
shizuku_post_ids_YYYY-MM-DD.txt の新規投稿を X ログへ統合してください。

条件:
1. logs/twitter(x)/ 以下の全アカウントの TSV と post_id を照合し、未収録 ID のみ処理すること。
2. FxTwitter は 1 件ずつ status（返信先欠損時は thread → conversation）で取得し、ページ連結は使わないこと。
3. @Shizuku_AItuber / @ShizukuResearch / tools/scripts/anon_whitelist.txt 等のホワイトリスト対象は実ハンドルを保持し、一般視聴者の reply_to_author は既存共通ソルトで匿名化（親本文は保存しない）すること。
4. author に対応するアカウントフォルダの 20 列 TSV（UTF-8 BOMなし・LF・date_utc 降順）を更新し、data/raw/x/ へ同じ相対パスで同期すること。
5. s1_normalize.py と doctor.py、既存テスト、git diff --check を実行し、ERROR 0 と検証結果を報告すること。
```
