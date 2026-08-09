# shizuku-pipeline — しずくwiki ログ処理ツールキット（モデルA: 手動運転版）

AI VTuber「しずく」のFandom wiki（紹介ページ・年表ページ）を、
蓄積ログから **人間の承認ゲートを通してだけ** 更新するための道具一式。

- 📖 使い方 → **MANUAL.md**（全体図・ステップ別手順・検証ポイント・運用カレンダー）
- 🩺 データ不備 → **DATA-ISSUES.md** ＋ `python scripts/doctor.py`（独立トラック）
- 🧠 Claudeに渡す指示 → `prompts/`（パック生成時に自動同梱）
- 標準ライブラリのみ。インストール不要。Python 3.9+
- 🤖 どのモデルで動かすか → MANUAL.md「4. LLMモデルの選び方」（工程ごとの要求水準と思考エフォート）
- 📦 gitに上げるもの/上げないもの → MANUAL.md「4. リポジトリ管理」（生成物は上げない、LLM出力と人間の判断は上げる）


## ドキュメント地図
- **CLAUDE.md** … AIエージェント引き継ぎガイド（まずこれ）。原則・コマンド・ゲート・変更時の注意。
- **MANUAL.md** … 人間向け操作手順（§0全体像〜§7トラブルシュート、§4モデル選び）。
- **docs/ARCHITECTURE.md** … 設計思想・データフロー・設計判断の理由。
- **docs/SPEC.md** … 契約（カード/台帳スキーマ・設定形式・ID体系・CLI・ゲート）。
- **docs/PLAN.md** … 現況スナップショット（実装済み・実測値・実データの特徴・修正履歴）。
- **docs/ROADMAP.md** … 今後の計画（校正→量産→ソース拡張→モデルB→強化）。
- **DATA-ISSUES.md** … データ不備の対処（doctor.py と対、§1〜§14）。

## 30秒クイックスタート（同梱データは処理済み）
```
cd shizuku-pipeline
python scripts/s3_match.py --list-open        # 台帳（未回収5→4件）を見る
python scripts/doctor.py                      # データ健診
less data/review/RV_20260808-01.md             # レビューパケットのデモ（記入済み）
less data/handoff/handoff_RV_20260808-01.txt   # wiki起草チャットへの受け渡し（デモ）
```
新しい配信が来たら: `s0_intake → s1_normalize → s2_pack → (Claude) → s2_ingest → s3 → s4 → 試聴チェック → s5`。
まとめて処理するときは `python scripts/s2_pack.py --all`（作業リスト `data/packs/WORKLIST.md` が作られます）。
詳細は MANUAL.md へ。

## 同梱の実データ処理結果
- 配信4本（2026-04-26 / 05-24 / 07-24 / 08-02）を正規化済み（文再結合・辞書・シグナル）
- Xログ2641件をJST変換・月別化済み（2026-01〜05）
- デモ一巡済み: カード9枚 → 台帳5件 → ギャルボイス願望(2026-02-28)がギャル配信(05-24)で回収成立 → handoff生成
- 名言候補1件は**あえて逐語未確定のまま**（試聴はあなたの工程、というゲートの実演）
