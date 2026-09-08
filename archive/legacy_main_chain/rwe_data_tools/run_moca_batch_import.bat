@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_moca_scores.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo MoCA batch processing completed.
) else (
  echo MoCA batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
