@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

rem ── 設定 ───────────────────────────────────────────────
rem AUTO_OPEN=0 なら処理完了後に出力フォルダを自動で開く（0 で無効）
set "AUTO_OPEN=1"

rem バッチファイルのある場所を基準にする（ショートカットから起動しても動くように）
pushd "%~dp0"

rem ── Python の実行方法を判定 ────────────────────────────
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (
    where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    echo [Error] Python が見つかりません。https://www.python.org/ からインストールしてください。
    pause
    popd
    exit /b 1
)

rem ── スクリプト本体の存在確認 ───────────────────────────
set "SCRIPT=%~dp0download_youtube_subtitles.py"
if not exist "%SCRIPT%" (
    echo [Error] download_youtube_subtitles.py が見つかりません:
    echo         %SCRIPT%
    pause
    popd
    exit /b 1
)

:start
cls
echo ==========================================
echo   YouTube Subtitle Downloader
echo ==========================================
echo.
echo 処理したいYouTube URLを1件ずつ入力してください。
echo 入力が終わったら、何も入力せずEnterを押してください。
echo.

set COUNT=0

rem URLを一時ファイルに書き出す（コマンドライン上限8191文字を回避）
set "TMPFILE=%TEMP%\yt_urls_%RANDOM%%RANDOM%.txt"
if exist "!TMPFILE!" del "!TMPFILE!"

:input_loop
set "NEXT_URL="
set /p "NEXT_URL=URL (空Enter で処理開始): "
if not defined NEXT_URL goto check_run
rem リダイレクトを先に書く: URL末尾が数字だと "1>>" がハンドル指定と誤解される不具合の回避
>>"!TMPFILE!" echo(!NEXT_URL!
set /a COUNT+=1
echo   -^> !COUNT! 件目を追加しました。
goto input_loop

:check_run
if !COUNT!==0 (
    echo.
    echo [Error] URLが1件も入力されていません。
    if exist "!TMPFILE!" del "!TMPFILE!"
    pause
    goto start
)

echo.
echo [Running] !COUNT! 件の動画をダウンロード中...
echo.
%PY% "%SCRIPT%" --file "!TMPFILE!"
set "RC=!ERRORLEVEL!"

rem 一時ファイルを削除
if exist "!TMPFILE!" del "!TMPFILE!"

echo.
echo ------------------------------------------
if "!RC!"=="0" (
    echo 処理が完了しました。
) else (
    echo [Warning] 一部の動画で失敗しました（終了コード !RC!）。
    echo           出力フォルダの _failed_urls.txt を確認してください。
)

rem ── 出力フォルダを自動で開く ───────────────────────────
if "%AUTO_OPEN%"=="1" (
    for /f "delims=" %%D in ('dir /b /ad /o-d "downloads_*" 2^>nul') do (
        start "" "%%~fD"
        goto after_open
    )
)
:after_open

echo.
set "CONTINUE="
set /p "CONTINUE=続けて別のURLを処理しますか？ (y = 続ける / それ以外で終了): "
if /i "!CONTINUE!"=="y" goto start

popd
endlocal
exit /b 0
