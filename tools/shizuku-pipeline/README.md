# shizuku-pipeline — しずくwiki ログ処理ツールキット（モデルA: 手動運転版）

AI VTuber「しずく」のFandom wiki（紹介ページ・年表ページ）を、
蓄積ログから **人間の承認ゲートを通してだけ** 更新するための道具一式。

- 📖 使い方 → **MANUAL.md**（全体図・ステップ別手順・検証ポイント・運用カレンダー）
- 🩺 データ不備 → **DATA-ISSUES.md** ＋ `python3 scripts/doctor.py`（独立トラック）
- 🧠 Claudeに渡す指示 → `prompts/`（パック生成時に自動同梱）
- 標準ライブラリのみ。インストール不要。Python 3.9+

## 30秒クイックスタート（同梱データは処理済み）
```
cd shizuku-pipeline
python3 scripts/s3_match.py --list-open        # 台帳（未回収5→4件）を見る
python3 scripts/doctor.py                      # データ健診
less data/review/RV_20260808-01.md             # レビューパケットのデモ（記入済み）
less data/handoff/handoff_RV_20260808-01.txt   # wiki起草チャットへの受け渡し（デモ）
```
新しい配信が来たら: `s0_intake → s1_normalize → s2_pack → (Claude) → s2_ingest → s3 → s4 → 試聴チェック → s5`。
詳細は MANUAL.md へ。

## 同梱の実データ処理結果
- 配信4本（2026-04-26 / 05-24 / 07-24 / 08-02）を正規化済み（文再結合・辞書・シグナル）
- Xログ2641件をJST変換・月別化済み（2026-01〜05）
- デモ一巡済み: カード9枚 → 台帳5件 → ギャルボイス願望(2026-02-28)がギャル配信(05-24)で回収成立 → handoff生成
- 名言候補1件は**あえて逐語未確定のまま**（試聴はあなたの工程、というゲートの実演）
