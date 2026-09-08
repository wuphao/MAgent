@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_cdr_scores.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo CDR batch processing completed.
) else (
  echo CDR batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
