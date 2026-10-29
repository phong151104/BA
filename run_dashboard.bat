@echo off
rem Start the Streamlit dashboard (Windows). The first run creates the Python 3.13 environment in .venv,
rem which takes a few minutes and needs the internet; later runs start at once. Close this window to stop.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating the Python 3.13 environment in .venv - first run only, a few minutes...
  py -3.13 -m venv .venv || goto :nopython
  ".venv\Scripts\python.exe" -m pip install -r requirements.lock.txt || goto :failed
  ".venv\Scripts\python.exe" -m pip install --no-deps -e . || goto :failed
)
echo Starting the dashboard at http://127.0.0.1:8501 ...
start "" cmd /c "timeout /t 6 /nobreak >nul & start http://127.0.0.1:8501"
".venv\Scripts\python.exe" -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
goto :eof

:nopython
echo Python 3.13 is needed: install it from https://www.python.org/downloads/ and run this file again.
pause
goto :eof

:failed
if exist ".venv" rmdir /s /q ".venv"
echo Installing the packages failed. Check the internet connection and run this file again.
pause
