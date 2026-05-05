@echo off
chcp 65001 > nul
setlocal

REM ── ドラッグ＆ドロップ チェック ──────────────────────────────────────────
if "%~1"=="" (
    echo.
    echo  使い方: .srt ファイルをこの .bat ファイルにドラッグ＆ドロップしてください。
    echo.
    pause
    exit /b 1
)

REM ── Python スクリプトのパス（この .bat と同じフォルダ） ──────────────────
set "SCRIPT=%~dp0srt_to_sbv.py"

if not exist "%SCRIPT%" (
    echo.
    echo  [エラー] srt_to_sbv.py が見つかりません。
    echo  このファイルと同じフォルダに srt_to_sbv.py を置いてください。
    echo  場所: %SCRIPT%
    echo.
    pause
    exit /b 1
)

REM ── 入力ファイルの拡張子チェック ─────────────────────────────────────────
if /i not "%~x1"==".srt" (
    echo.
    echo  [エラー] .srt ファイル以外はサポートしていません。
    echo  指定されたファイル: %~1
    echo.
    pause
    exit /b 1
)

REM ── 出力パス: 入力ファイルと同じフォルダ・同じ名前で .sbv ────────────────
set "INPUT=%~1"
set "OUTPUT=%~dpn1.sbv"

echo.
echo  変換中...
echo  入力: %INPUT%
echo  出力: %OUTPUT%
echo.

python "%SCRIPT%" "%INPUT%" "%OUTPUT%"

if errorlevel 1 (
    echo.
    echo  [エラー] 変換に失敗しました。
) else (
    echo.
    echo  完了しました！
)

echo.
pause
endlocal
