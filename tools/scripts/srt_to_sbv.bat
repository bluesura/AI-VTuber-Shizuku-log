@echo off
chcp 65001 > nul
setlocal

REM ── ドラッグ＆ドロップ チェック ──────────────────────────────────────────
if "%~1"=="" (
    echo.
    echo  使い方: .srt ファイルをこの .bat にドラッグ ^& ドロップしてください。
    echo.
    pause
    exit /b 1
)

set "SCRIPT=%~dp0srt_to_sbv.py"

if not exist "%SCRIPT%" (
    echo.
    echo  [エラー] srt_to_sbv.py が見つかりません。
    echo  この .bat と同じフォルダに置いてください。
    echo  場所: %SCRIPT%
    echo.
    pause
    exit /b 1
)

if /i not "%~x1"==".srt" (
    echo.
    echo  [エラー] .srt ファイル以外はサポートしていません。
    echo  指定されたファイル: %~1
    echo.
    pause
    exit /b 1
)

set "INPUT=%~1"
set "OUTPUT=%~dpn1.sbv.txt"

echo.
echo  変換中...
echo  入力: %INPUT%
echo  出力: %OUTPUT%
echo.

python "%SCRIPT%" "%INPUT%" "%OUTPUT%"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo  完了しました。すべて検証済みです。
) else if "%RC%"=="3" (
    echo  完了しましたが、断定できない箇所がありました。
    echo  監査ログを確認してください: %OUTPUT%.audit.txt
    echo  ※ 該当箇所は削除せず残してあります。
) else if "%RC%"=="2" (
    echo  [中止] 断定できない箇所があったため変換を中止しました。
    echo  出力ファイルは作成していません。
) else (
    echo  [エラー] 変換に失敗しました。上のメッセージを確認してください。
)

echo.
pause
endlocal
