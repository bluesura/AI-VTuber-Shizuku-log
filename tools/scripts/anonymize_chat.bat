@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM ── ドラッグ＆ドロップ チェック ──────────────────────────────────────────
if "%~1" == "" (
    echo.
    echo  使い方: .txt ファイルをこの .bat ファイルにドラッグ＆ドロップしてください。
    echo.
    pause
    exit /b 1
)

REM ── Python スクリプトのパス ──────────────────
set "SCRIPT=%~dp0anonymize_chat.py"

if not exist "!SCRIPT!" (
    echo.
    echo  [エラー] anonymize_chat.py が見つかりません。
    pause
    exit /b 1
)

REM ── 入力ファイルの拡張子チェック ─────────────────────────────────────────
if /i not "%~x1" == ".txt" (
    echo.
    echo  [エラー] .txt ファイル以外はサポートしていません。
    pause
    exit /b 1
)

set "INPUT=%~1"

echo.
echo  匿名化処理中...
REM 遅延展開 (!変数!) を使うことで、パス中の記号による誤作動を防ぎます
echo  入力: "!INPUT!"
echo.

python "!SCRIPT!" "!INPUT!"

if errorlevel 1 (
    echo.
    echo  [エラー] 処理に失敗しました。
) else (
    echo.
    echo  完了しました！
)

echo.
pause
endlocal