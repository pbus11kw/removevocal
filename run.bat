@echo off

REM Get the directory of the batch file
set "BATCH_DIR=%~dp0"

REM Activate the virtual environment
echo Activating virtual environment...
call "%BATCH_DIR%venv\Scripts\activate.bat"

REM Check if activation was successful
if errorlevel 1 (
    echo Failed to activate virtual environment. Exiting.
    pause
    exit /b 1
)

echo Starting Uvicorn server...
REM Run the uvicorn server
uvicorn main:app --reload --host 0.0.0.0

REM Deactivate the virtual environment (optional, runs when server is stopped)
call "%BATCH_DIR%venv\Scripts\deactivate.bat"
