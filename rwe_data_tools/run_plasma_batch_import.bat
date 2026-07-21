@echo off
setlocal
cd /d "%~dp0"
python "%~dp0import_plasma_biomarkers.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Plasma biomarker batch processing completed.
) else (
  echo Plasma biomarker batch processing completed with errors. Exit code: %EXIT_CODE%
)
exit /b %EXIT_CODE%
