@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_haass_washu_lab.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Haass/WashU batch processing completed.
) else (
  echo Haass/WashU batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
