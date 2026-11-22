# 第三者コード・考え方の出典と同梱範囲

- **yomiyasu** — https://github.com/nanaism/yomiyasu  / MIT (Copyright 2026 nanaism)。参照版: 2026-11-03確認時点の`skills/yomiyasu/SKILL.md`（GitHub blob SHA `5cca6b8bb495a81bfcefb579d05c0e5f52d4fb1f`）。このv2には原本コード・原本の全手順をコピーせず、`yomiyasu-adapter.md`に意味保持等の原則をWiki向けに再構成している。ライセンス文は`licenses/yomiyasu-LICENSE`。
- **deslop-ja** — https://github.com/nakashimatakaya/deslop-ja / MIT (Copyright 2026 Takaya Nakashima)。ユーザー添付`deslop-ja-main.zip`から`check.py`をそのまま同梱。文章パターンの**診断のみ**で使用し、`SKILL.md`にある編集指示を自動起動しない。ライセンス文は`licenses/deslop-ja-LICENSE`。
- **natural-japanese** — https://github.com/coji/natural-japanese / MIT (Copyright 2026 coji)。ユーザー添付`natural-japanese-main.zip`から`paragraphs.py`, `newfacts.py`, `textcore.py`, `lint.py`をそのまま同梱。`paragraphs.py`はPython標準ライブラリのみ。`newfacts.py`はSudachiPy/dictが必要な任意ツール。研究用の文章コーパスや外部データは同梱しない。ライセンス文は`licenses/natural-japanese-LICENSE`。

注意：この配布版は3つの元Skillを独立したAgent Skillとして全部インストールするものではない。Wiki統括Skillの内部で役割を絞って使用する移植版。上流の更新を追従するときは取り込み版、変更差分、ライセンス表示を確認する。しずくWiki本文をライセンスファイルに含めない。
