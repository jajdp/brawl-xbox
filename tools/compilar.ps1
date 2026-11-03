<#
.SYNOPSIS
  Rehace el port UWP de Super Smash Bros. Brawl para la Xbox Series X, paso a paso.

.DESCRIPTION
  Pasos, en orden:

    overlay     copia runtime\, aurora-main\ y projects\ de -Wiicompiled a -Build\port
    parchar     aplica los 52 parches de fase0\parchar_uwp.py sobre ese overlay
    compdb      regenera -Build\compile_commands.json con `ninja -t compdb`
    compilar    compila las 1.253 unidades con clang ABI-MSVC (fase0\lanzar.cmd)
    enlazar     enlaza SuperSmashBrosBrawl.exe con lld (fase0\enlazar.cmd)
    semilla     arma la semilla 0.1.0.0 (solo para la PRIMERA instalacion en una consola)
    empaquetar  arma y firma el .msix
    todo        overlay -> empaquetar

  ⚠ `overlay` y `parchar` van juntos y en ese orden: el parchador NO es idempotente en dos puntos
  (main.cpp y host_cpu_baseline.cpp llevan parches en cascada), asi que hay que aplicarlo de una
  pasada sobre un arbol limpio. Por eso `overlay` usa robocopy /IS /IT, que fuerza la copia.

.EXAMPLE
  pwsh -File compilar.ps1 todo
  pwsh -File compilar.ps1 compilar -Jobs 24
  pwsh -File compilar.ps1 enlazar
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('overlay', 'parchar', 'compdb', 'compilar', 'enlazar', 'semilla', 'empaquetar', 'todo')]
    [string]$Paso,
    # El arbol de WiiCompiled ya compilado para PC (el que tiene runtime\, aurora-main\, projects\).
    [Parameter(Mandatory = $true)][string]$Wiicompiled,
    # Carpeta de trabajo del port: aqui van el overlay parcheado, los objetos y el .msix.
    [Parameter(Mandatory = $true)][string]$Build,
    [int]$Jobs = 20,
    [string]$Version = '0.1.0.1'
)
$ErrorActionPreference = 'Stop'

$xbox = $PSScriptRoot
$fase0 = $PSScriptRoot        # en el repositorio publicado todo vive junto, en tools\
$arbol = $Wiicompiled
$uwp = $Build
$overlay = Join-Path $uwp 'port'
$obj = Join-Path $uwp 'obj'
$build = Join-Path $uwp 'build'
$compdb = Join-Path $uwp 'compile_commands.json'
$exe = Join-Path $build 'SuperSmashBrosBrawl.exe'
$msix = Join-Path $build "WiiCompiled-SuperSmashBrosBrawl_${Version}_x64.msix"

function Paso-Overlay {
    "== overlay: copiando el arbol limpio a $overlay"
    New-Item -ItemType Directory -Force -Path $overlay | Out-Null
    foreach ($sub in @('runtime', 'aurora-main', 'projects')) {
        robocopy "$arbol\$sub" "$overlay\$sub" /E /IS /IT /NFL /NDL /NJH /NJS /NP `
            /XD build native-build .git /R:1 /W:1 | Out-Null
    }
    # Lo que el overlay aporta y el arbol no tiene.
    Copy-Item "$arbol\generated\RuntimeConfig.h" (Join-Path $overlay 'generated\RuntimeConfig.h') -Force
    Copy-Item (Join-Path $fase0 'uwp_main.cpp') (Join-Path $overlay 'runtime\src\uwp_main.cpp') -Force -ErrorAction SilentlyContinue
    "   listo"
}

function Paso-Parchar {
    "== parchar: aplicando la receta de una pasada"
    py -3.13 -X utf8 (Join-Path $fase0 'parchar_uwp.py') $overlay | Select-Object -Last 1
    if ($LASTEXITCODE) { throw 'el parchador reporto fallos' }
}

function Paso-Compdb {
    "== compdb: regenerando la base de compilacion"
    Push-Location (Join-Path $arbol 'native-build')
    try { & (Join-Path $Wiicompiled 'toolchain\Ninja\ninja.exe') -t compdb | Set-Content -LiteralPath $compdb -Encoding utf8 }
    finally { Pop-Location }
    "   {0:N1} MB" -f ((Get-Item -LiteralPath $compdb).Length / 1MB)
}

function Paso-Compilar {
    "== compilar: 1.253 unidades con clang ABI-MSVC, jobs=$Jobs"
    New-Item -ItemType Directory -Force -Path $obj | Out-Null
    $linea = '"{0}" "{1}" "{2}" --jobs {3} --solo=runtime,aurora,generated,third_party,deps --overlay={4}' -f `
        (Join-Path $fase0 'lanzar.cmd'), $compdb, $obj, $Jobs, ($overlay -replace '\\', '/')
    & cmd /c $linea
}

function Paso-Enlazar {
    "== enlazar: lld, un solo binario con todo dentro"
    New-Item -ItemType Directory -Force -Path $build | Out-Null
    & cmd /c ('"{0}" "{1}" "{1}" "{2}"' -f (Join-Path $fase0 'enlazar.cmd'), $obj, $exe)
    if (-not (Test-Path $exe)) { throw 'no se enlazo el ejecutable' }
    "   {0:N1} MB" -f ((Get-Item -LiteralPath $exe).Length / 1MB)
}

function Paso-Semilla {
    "== semilla: para la PRIMERA instalacion en una consola (D:\DevelopmentFiles esta lleno)"
    pwsh -NoProfile -File (Join-Path $fase0 'semilla.ps1') | Select-Object -Last 2
}

function Paso-Empaquetar {
    "== empaquetar: .msix firmado"
    py -3.13 -X utf8 (Join-Path $fase0 'empaquetar_uwp.py') $exe $msix | Select-Object -Last 2
}

switch ($Paso) {
    'overlay' { Paso-Overlay }
    'parchar' { Paso-Parchar }
    'compdb' { Paso-Compdb }
    'compilar' { Paso-Compilar }
    'enlazar' { Paso-Enlazar }
    'semilla' { Paso-Semilla }
    'empaquetar' { Paso-Empaquetar }
    'todo' {
        Paso-Overlay; Paso-Parchar; Paso-Compdb; Paso-Compilar; Paso-Enlazar; Paso-Empaquetar
    }
}
