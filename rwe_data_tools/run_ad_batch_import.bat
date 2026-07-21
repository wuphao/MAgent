@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_dicom_basic_info.py" --source-dir "D:\data\adni_diamond\AD" --diagnosis AD --all-patients %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo AD batch processing completed.
) else (
  echo AD batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
