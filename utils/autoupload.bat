@echo on
chcp 65001 >nul
setlocal enableextensions

set "BASE=C:\Users\ngrin\Desktop\code\tiktokupload"
set "LOG=%BASE%\task_stdout.log"
set "PY_VENV=%BASE%\venv\Scripts\python.exe"
set "PY_FALLBACK=C:\Python313\python.exe"

cd /d "%BASE%" || exit /b 1
echo ==== %date% %time% START ====>>"%LOG%"

REM --- 1) Ждём сеть после пробуждения (до 90 сек) ---
set /a tries=0
:WAITNET
ping -n 1 1.1.1.1 >nul 2>&1 && goto NETOK
set /a tries+=1
if %tries% GEQ 30 goto NETFAIL
timeout /t 3 /nobreak >nul
goto WAITNET
:NETOK
echo Network: OK >>"%LOG%"
goto RUN
:NETFAIL
echo Network: TIMEOUT >>"%LOG%"

:RUN
REM --- 2) Выбираем Python (venv приоритетно) ---
if exist "%PY_VENV%" (set "PY=%PY_VENV%") else (set "PY=%PY_FALLBACK%")
"%PY%" -V >>"%LOG%" 2>&1
"%PY%" -c "import sys,os; print('cwd=',os.getcwd()); print('py=',sys.executable)" >>"%LOG%" 2>&1

REM --- 3) Запуск скрипта ---
"%PY%" "%BASE%\final_upload.py" >>"%LOG%" 2>&1
echo EXITCODE=%errorlevel% >>"%LOG%"
echo ==== %date% %time% END ====>>"%LOG%"
exit /b %errorlevel%
