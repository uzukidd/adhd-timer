@echo off
setlocal
cd /d "%~dp0.."
where conda >nul 2>nul
if errorlevel 1 (
    echo Conda was not found. Run this script from Anaconda Prompt.
    exit /b 1
)
rem Install build dependencies, build the EXE, verify it, and create a ZIP.
call conda run --no-capture-output -n adhd-timer python scripts\build.py %*
set "BUILD_EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %BUILD_EXIT_CODE%
