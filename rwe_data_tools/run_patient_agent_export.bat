@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: %~nx0 PATIENT_NUMBER [extra options]
  echo Example: %~nx0 041_S_4060
  exit /b 2
)
set "PATIENT_NUMBER=%~1"
shift
python "%~dp0export_patient_agent_json.py" --patient-number "%PATIENT_NUMBER%" %*
exit /b %ERRORLEVEL%
