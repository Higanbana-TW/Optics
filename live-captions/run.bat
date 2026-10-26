@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

if exist .venv\Scripts\python.exe goto have_venv
if exist .venv (
  echo 發現不完整的 .venv，正在刪除。不會把它當成安裝成功。
  rmdir /s /q .venv
)
if exist .venv goto venv_fail

call :resolve_python
if errorlevel 1 goto python_exit
echo 正在建立虛擬環境...
"%PY_EXE%" -m venv .venv
if errorlevel 1 goto venv_fail
if not exist .venv\Scripts\python.exe goto venv_fail

:have_venv
call :check_interpreter ".venv\Scripts\python.exe"
if errorlevel 1 goto python_exit
".venv\Scripts\python.exe" -c "import numpy" >nul 2>&1
if errorlevel 1 goto install_reqs
goto run_app

:install_reqs
echo 虛擬環境裡還沒有 numpy，正在安裝 requirements.txt ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto pip_fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto pip_fail

:run_app
".venv\Scripts\python.exe" -m live_captions %*
if errorlevel 1 goto app_fail
exit /b 0

:python_exit
echo.
if "%PY_REASON%"=="wrong" goto msg_wrong
if "%PY_REASON%"=="store" goto msg_store
goto msg_missing

:msg_wrong
echo 無法繼續：現在的 Python 不是 64 位元的 Python 3.12。
echo 32 位元，或 3.13、3.14 這類其他版本，沒有對應的 onnxruntime 套件。
echo pip 會因此出現 ResolutionImpossible。這次不會建立虛擬環境，也不會開始安裝。
echo.
echo 請安裝 64 位元 Python 3.12，並勾選 "Add python.exe to PATH"：
echo https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
echo.
echo 若 live-captions\.venv 已經存在，請先刪除該資料夾再重新執行 run.bat。
goto fail_pause

:msg_store
echo 找不到真正的 Python。python.exe 或 python3.exe 是 Microsoft Store 的應用程式執行別名。
echo.
echo 請安裝 64 位元 Python 3.12，並勾選 "Add python.exe to PATH"：
echo https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
echo.
echo 然後到設定、應用程式、進階應用程式設定、應用程式執行別名，
echo 關閉 python.exe 與 python3.exe。
goto fail_pause

:msg_missing
echo 找不到 Python。字幕程式尚未啟動。
echo.
echo 請安裝 64 位元 Python 3.12，並勾選 "Add python.exe to PATH"：
echo https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
echo.
echo 若 python 指令會打開 Microsoft Store，請到
echo 設定、應用程式、進階應用程式設定、應用程式執行別名，
echo 關閉 python.exe 與 python3.exe。
goto fail_pause

:venv_fail
echo.
echo 建立虛擬環境失敗，不視為安裝成功。字幕程式尚未啟動。
echo 請安裝 64 位元 Python 3.12：
echo https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
echo 並刪除 live-captions\.venv 後再執行 run.bat。
goto fail_pause

:pip_fail
echo.
echo 套件安裝失敗，字幕程式尚未啟動。
echo 若上面出現 ResolutionImpossible 或 onnxruntime，代表 Python 不是 64 位元 3.12。
echo 請改安裝：
echo https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
echo 然後刪除 live-captions\.venv 再執行 run.bat。
goto fail_pause

:app_fail
echo.
echo 字幕程式沒有順利開啟。請先看上面的錯誤訊息。
goto fail_pause

:fail_pause
echo.
pause
exit /b 1

:resolve_python
set "PY_EXE="
set "PY_REASON="
set "STORE_STUB="
where py >nul 2>&1
if errorlevel 1 goto try_python_exe
for /f "delims=" %%E in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%E"
if defined PY_EXE goto resolve_check
for /f "delims=" %%E in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%E"
if defined PY_EXE goto resolve_check
:try_python_exe
for /f "delims=" %%I in ('where python 2^>nul') do (
  if not defined PY_EXE (
    echo %%I | find /I "\WindowsApps\" >nul
    if errorlevel 1 (
      set "PY_EXE=%%I"
    ) else (
      set "STORE_STUB=1"
    )
  )
)
if defined PY_EXE goto resolve_check
if defined STORE_STUB goto resolve_store
set "PY_REASON=missing"
exit /b 1
:resolve_store
set "PY_REASON=store"
exit /b 1
:resolve_check
echo %PY_EXE% | find /I "\WindowsApps\" >nul
if not errorlevel 1 goto resolve_store
call :check_interpreter "%PY_EXE%"
if errorlevel 1 exit /b 1
exit /b 0

:check_interpreter
set "CHECK_EXE=%~1"
echo %CHECK_EXE% | find /I "\WindowsApps\" >nul
if not errorlevel 1 goto check_store
"%CHECK_EXE%" -c "import struct,sys; bits=struct.calcsize('P')*8; raise SystemExit(0 if sys.version_info[:2]==(3,12) and bits==64 else 2 if bits!=64 else 3)"
if errorlevel 2 goto check_wrong
if errorlevel 1 goto check_missing
exit /b 0
:check_store
set "PY_REASON=store"
exit /b 1
:check_wrong
set "PY_REASON=wrong"
exit /b 1
:check_missing
set "PY_REASON=missing"
exit /b 1
