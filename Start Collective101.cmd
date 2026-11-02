@echo off
cd /d "%~dp0"
echo Open http://127.0.0.1:8765 after the server starts.
echo If it is already running, use that URL in your browser.
python -m collective101 --state .collective101/console.db serve --port 8765
pause
