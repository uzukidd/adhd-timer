@echo off
setlocal
cd /d "%~dp0.."
conda run -n adhd-timer python -m focus_flow.app
endlocal
