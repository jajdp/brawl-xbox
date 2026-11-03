@echo off
rem Fase 1: entra al entorno «store» (UWP) de Visual Studio y enlaza con lld.
rem El entorno hace falta por LIB: lld toma de ahi WindowsApp.lib y el CRT de la tienda.
rem Uso: enlazar.cmd <carpeta_obj> <carpeta_obj_2> <salida.exe> [--excluir=a,b]
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 store >nul
if errorlevel 1 (echo vcvarsall fallo & exit /b 1)
py -3.13 -X utf8 "%~dp0enlazar_uwp.py" %*
