@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

rem バッチのある場所を基準にする（ショートカット経由でも動くように）
pushd "%~dp0"

rem ── 引数チェック（ドラッグ＆ドロップ）─────────────────────
if "%~1"=="" goto no_arg

set "SCRIPT=%~dp0srt_to_sbv.py"
if not exist "!SCRIPT!" goto no_script

if /i not "%~x1"==".srt" goto bad_ext

rem ── Python の実行方法を判定 ───────────────────────────────
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (
    where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY goto no_python

set "INPUT=%~1"
set "OUTPUT=%~dpn1.sbv.txt"

echo.
echo  変換中...
echo  入力: "!INPUT!"
echo  出力: "!OUTPUT!"
echo.

rem パスは必ず引用符で囲む（括弧やスペースを含む場所でも壊れないように）
!PY! "!SCRIPT!" "!INPUT!" "!OUTPUT!"
set "RC=!ERRORLEVEL!"

echo.
rem 括弧ブロックの中でパス変数を展開しないよう、分岐は goto で行う
if "!RC!"=="0" goto ok
if "!RC!"=="3" goto warned
if "!RC!"=="2" goto aborted
goto failed

:ok
echo  完了しました。すべて検証済みです。
echo  （[音楽] を削除した明細があれば下記に記録されています）
echo    "!OUTPUT!.audit.txt"
goto end

:warned
echo  完了しましたが、断定できない箇所がありました。
echo  監査ログを確認してください:
echo    "!OUTPUT!.audit.txt"
echo  ※ 該当箇所は削除せず残してあります。
goto end

:aborted
echo  [中止] 断定できない箇所があったため変換を中止しました。
echo  出力ファイルは作成していません。
goto end

:failed
echo  [エラー] 変換に失敗しました。上のメッセージを確認してください。
goto end

:no_arg
echo.
echo  使い方: .srt ファイルをこの .bat にドラッグ ^& ドロップしてください。
goto end

:no_script
echo.
echo  [エラー] srt_to_sbv.py が見つかりません。
echo  この .bat と同じフォルダに置いてください。
echo  場所:
echo    "!SCRIPT!"
goto end

:bad_ext
echo.
echo  [エラー] .srt ファイル以外はサポートしていません。
echo  指定されたファイル:
echo    "%~1"
goto end

:no_python
echo.
echo  [エラー] Python が見つかりません。
echo  https://www.python.org/ からインストールしてください。
echo  （インストーラーの "Add Python to PATH" にチェックを入れると確実です）
goto end

:end
echo.
pause
popd
endlocal
