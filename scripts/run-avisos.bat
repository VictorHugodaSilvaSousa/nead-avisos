@echo off
rem NEAD Avisos - uma verificacao (usada pelo Agendador de Tarefas e para teste manual).
setlocal
cd /d "%~dp0.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist "data" mkdir "data"
".venv\Scripts\nead-avisos.exe" run %* >> "data\avisos.log" 2>&1
exit /b %ERRORLEVEL%
