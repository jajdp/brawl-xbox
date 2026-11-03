<#
.SYNOPSIS
  Arma y firma la SEMILLA del paquete: la misma identidad en la version 0.1.0.0, con el manifiesto
  y los mosaicos de verdad y un ejecutable minimo.

.DESCRIPTION
  La primera instalacion de una familia nueva en la la consola va a D:\DevelopmentFiles
  (5 GB casi llenos) y falla con «There is not enough space on the disk» (-2147024784). Las
  actualizaciones de una familia YA registrada van a otro almacenamiento. Por eso: semilla
  pequena primero, y el paquete completo encima como actualizacion (0.1.0.1).

  Hay que correrlo desde el entorno «store» de Visual Studio (lo entra el mismo script).

.EXAMPLE
  pwsh -File semilla.ps1
#>
[CmdletBinding()]
param(
    [string]$Trabajo = (Join-Path $env:TEMP 'brawl-semilla'),
    [string]$Version = '0.1.0.0'
)
$ErrorActionPreference = 'Stop'

$fase0 = $PSScriptRoot
$xbox = Split-Path $fase0 -Parent
$paquete = Join-Path $xbox 'package'
$clang = Join-Path $env:BRAWL_LLVM_MINGW 'bin\clang.exe'
$sdk = 'C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64'
$huella = $env:BRAWL_CERT_THUMBPRINT
$depot = Join-Path $env:BRAWL_UWP_DEP 'x64'

New-Item -ItemType Directory -Force -Path $Trabajo | Out-Null
$contenido = Join-Path $Trabajo 'contenido'
if (Test-Path $contenido) { Remove-Item -LiteralPath $contenido -Recurse -Force }
New-Item -ItemType Directory -Force -Path $contenido | Out-Null

# 1. El ejecutable minimo, con el ABI de MSVC y marcado como AppContainer.
$obj = Join-Path $Trabajo 'semilla.obj'
$exe = Join-Path $Trabajo 'SuperSmashBrosBrawl.exe'
$vcvars = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat'
$ordenes = @(
    "call `"$vcvars`" x64 store >nul",
    "`"$clang`" --target=x86_64-pc-windows-msvc -fms-runtime-lib=dll -DWINAPI_FAMILY=WINAPI_FAMILY_APP -c `"$(Join-Path $fase0 'semilla.cpp')`" -o `"$obj`"",
    "`"$($clang -replace 'clang\.exe$','ld.lld.exe')`" -flavor link /nologo /machine:x64 /subsystem:windows,10.0 /appcontainer /dynamicbase /nxcompat /out:`"$exe`" `"$obj`" WindowsApp.lib msvcrt.lib vcruntime.lib ucrt.lib"
) -join ' && '
cmd /c $ordenes
if (-not (Test-Path $exe)) { throw 'no se enlazo el exe de la semilla' }
"exe de la semilla: {0:N0} B" -f (Get-Item -LiteralPath $exe).Length

# 2. El manifiesto de verdad, con la version de la semilla.
$man = Get-Content -LiteralPath (Join-Path $paquete 'Package.appxmanifest') -Raw
$nuevo = [regex]::Replace($man, '(<Identity[^>]*?Version=")[^"]+(")', "`${1}$Version`${2}")
if ($nuevo -eq $man -and $man -notmatch [regex]::Escape("Version=`"$Version`"")) {
    throw 'no encontre la version en la identidad del manifiesto'
}
[System.IO.File]::WriteAllText((Join-Path $contenido 'AppxManifest.xml'), $nuevo)
Copy-Item -LiteralPath (Join-Path $paquete 'Assets') -Destination (Join-Path $contenido 'Assets') -Recurse

# 3. El exe y libuwp, que es lo unico que la semilla necesita al lado: el manifiesto declara
#    EntryPoint="uwp.App", que vive en libuwp. Sin el exe, makeappx responde
#    «The package manifest is not valid» (0x80080204) y no dice que falte un archivo.
Copy-Item -LiteralPath $exe -Destination $contenido
Copy-Item -LiteralPath (Join-Path $depot 'bin\libuwp.dll') -Destination $contenido

# 4. Empaquetar y firmar.
$msix = Join-Path $Trabajo "WiiCompiled-SuperSmashBrosBrawl_${Version}_x64-semilla.msix"
if (Test-Path $msix) { Remove-Item -LiteralPath $msix -Force }
& (Join-Path $sdk 'makeappx.exe') pack /o /d $contenido /p $msix | Select-Object -Last 3
if ($LASTEXITCODE) { throw 'makeappx fallo (semilla)' }
& (Join-Path $sdk 'signtool.exe') sign /fd SHA256 /sha1 $huella /s My $msix | Select-Object -Last 2
if ($LASTEXITCODE) { throw 'signtool fallo (semilla)' }
"semilla lista: $msix ({0:N0} B)" -f (Get-Item -LiteralPath $msix).Length
