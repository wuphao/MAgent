@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_apoe_genotype.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo APOE batch processing completed.
) else (
  echo APOE batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
