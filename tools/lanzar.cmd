@echo off
rem Fase 0: entra al entorno «store» (UWP) de Visual Studio y corre el compile-check.
rem Uso: lanzar.cmd <compdb.json> <carpeta_salida> [--jobs N] [--solo=grupos]
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 store >nul
if errorlevel 1 (echo vcvarsall fallo & exit /b 1)
echo INCLUDE=%INCLUDE%
echo LIB=%LIB%
py -3.13 -X utf8 "%~dp0compile_check.py" %*
