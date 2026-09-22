@echo off
setlocal
cd /d "%~dp0.."
set "CONDA_EXE=D:\miniconda3\Scripts\conda.exe"
"%CONDA_EXE%" run -n adhd-timer python -m focus_flow.app
endlocal
