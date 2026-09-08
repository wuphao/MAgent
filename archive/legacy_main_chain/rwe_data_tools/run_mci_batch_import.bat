@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_dicom_basic_info.py" --all-patients %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Batch processing completed.
) else (
  echo Batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
