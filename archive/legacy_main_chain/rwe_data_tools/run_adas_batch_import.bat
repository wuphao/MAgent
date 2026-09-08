@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_adas_scores.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo ADAS batch processing completed.
) else (
  echo ADAS batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
