# 横断検証CLI

リポジトリのルートから実行する。出典の逐語性と主張の裏付けは人間が確認する。

| CLI | 対象 |
|---|---|
| `verify_citations.py <カードJSONL／handoff／Wiki下書き> ...` | YouTube・Xのローカル出典。Xの未同期、字幕やチャットの未正規化、対象IDの未収録を報告 |
| `sweep_text.py <公開用本文> ...` | 未完了タグ、プレースホルダー、未復元マーカー、匿名化候補。通常の編集メモと引用中の演出表現は許容。匿名化候補も終了コードに含める場合は `--strict` |
| `verify_roundtrip.py <前> <後> --format jsonl` | 多重集合で欠落検知。TSV、行キー、Wiki動画一覧、年表はそれぞれ `tsv`、`lines`、`wiki-videos`、`wiki-timeline`。承認済み変更は `--allow-removal <キー>` で個別指定 |
| `check_persona_consistency.py <下書き> --facts <確認済みTSV>` | `field`、`value`、`source` の3列で人が確認した属性だけを照合。ペルソナ資料の下書きや更新提案から確定属性を生成する工程は手動 |
| `clean_cache.py --dry-run` | 再生成できるPythonバイトコードのパス、サイズ、理由。保存後の内容確認が済んだASRでは `--run <専用実行フォルダ>` で完了記録と保存本文を照合して動画・音声を列挙 |

例

```powershell
python tools/scripts/verify/verify_citations.py tools/shizuku-pipeline/data/cards/2023-02.jsonl
python tools/scripts/verify/verify_roundtrip.py before.wiki after.wiki --format wiki-timeline
python tools/scripts/verify/clean_cache.py --dry-run
```

開始前チャットのカードは符号付き秒で照合する。URLだけが0秒に丸められ、近くに本編の記録が見つからない場合は元時刻の確認を求める。Xの正規化を再構築する前には `s1_normalize.py --x --dry-run` で全月の出力候補を確認できる。

整理で削除できるのは表示した候補だけ。ユーザーが削除を承認した場合に限り `--execute` を指定する。ASRの旧実行は完了記録がなければ保護される。Wikiの承認・同期・失敗記録、一次ログ、カード・台帳・レビュー・進捗は保護対象。
