@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

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
set TMPFILE=%TEMP%\yt_urls_%RANDOM%.txt
if exist "!TMPFILE!" del "!TMPFILE!"

:input_loop
set NEXT_URL=
set /p "NEXT_URL=URL (空Enter で処理開始): "
if "!NEXT_URL!"=="" goto check_run
set /a COUNT+=1
echo !NEXT_URL!>> "!TMPFILE!"
echo   -> !COUNT! 件目を追加しました。
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
python download_youtube_subtitles.py --file "!TMPFILE!"

rem 一時ファイルを削除
if exist "!TMPFILE!" del "!TMPFILE!"

echo.
echo ------------------------------------------
echo 処理が完了しました。
echo.
set /p "CONTINUE=続けて別のURLを処理しますか？ (y/n): "
if /i "!CONTINUE!"=="y" goto start

exit