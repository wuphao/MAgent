@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_faq_scores.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo FAQ batch processing completed.
) else (
  echo FAQ batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
