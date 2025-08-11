@echo off
setlocal
cd /d "C:\Users\ngrin\Desktop\code\tiktokupload"

REM Лог в той же папке
set LOGFILE=task_stdout.log

echo ==== %date% %time% START ==== >> "%LOGFILE%"
"C:\Python313\python.exe" "final_upload.py" >> "%LOGFILE%" 2>&1
echo EXITCODE=%ERRORLEVEL% >> "%LOGFILE%"
echo ==== %date% %time% END ==== >> "%LOGFILE%"
