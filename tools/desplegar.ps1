<#
.SYNOPSIS
  Instala el port de Brawl en la Xbox Series X, sube lo que necesita y lo lanza.

.DESCRIPTION
  Pasos (todos opcionales por parametro):

    instalar   sube el .msix y lo despliega por el Device Portal
    config     copia el Config.toml a \LocalState\WiiCompiled
    disco      sube el disco extraido a \LocalState\GameAssets\DATA (por lotes y en ZIP)
    lanzar     arranca el juego y deja una captura en xbox\capturas
    todo       los cuatro, en ese orden

  ⚠ TRES cosas que ya costaron caro y estan resueltas aqui:

  1. **La PRIMERA instalacion de la familia** va a D:\DevelopmentFiles (5 GB casi llenos) y falla
     con «There is not enough space on the disk». Hay que instalar antes la semilla
     (`fase0\semilla.ps1`) y el paquete completo encima, como actualizacion. -Semilla lo hace.

  2. **El espacio de desarrollo son 30 GB FIJOS** para todos los ports juntos (medido desde
     dentro: «libre 0 MiB de 30719 MiB»), y no tiene nada que ver con los 802 GB del
     almacenamiento de juegos. El disco de Brawl son 6,7 GB: hay que tener sitio ANTES.
     Para hacerlo: `herramientas\xbox-vaciar-carpeta.ps1` sobre el GameAssets de otro port.

  3. **Lanzar por el portal falla a veces** con -2147023880 y al segundo intento va. Se reintenta.

.EXAMPLE
  pwsh -File desplegar.ps1 -Paso todo -Semilla
  pwsh -File desplegar.ps1 -Paso lanzar
#>
[CmdletBinding()]
param(
    [ValidateSet('instalar', 'config', 'disco', 'lanzar', 'todo')]
    [string]$Paso = 'todo',
    [Parameter(Mandatory = $true)][string]$Host_,
    # Carpeta de trabajo del port, la misma que se le dio a compilar.ps1: de ahi sale el .msix.
    [Parameter(Mandatory = $true)][string]$Build,
    # El disco extraido con el que se construyo (su carpeta DATA), para el paso 'disco'.
    [string]$Disco,
    [string]$Version = '0.1.0.3',
    [switch]$Semilla
)
$ErrorActionPreference = 'Stop'

$xbox = $PSScriptRoot
$fase0 = $PSScriptRoot        # en el repositorio publicado todo vive junto, en tools\
$capturas = Join-Path $xbox 'capturas'
$portal = Join-Path $PSScriptRoot 'xbox-portal.ps1'
$msix = Join-Path $Build "WiiCompiled-SuperSmashBrosBrawl_${Version}_x64.msix"
$pfn = "WiiCompiled-SuperSmashBrosBrawl_${Version}_x64__mk2h16as9zg4e"
$appid = 'WiiCompiled-SuperSmashBrosBrawl_mk2h16as9zg4e!App'

function Portal { pwsh -NoProfile -File $portal @args }

function Paso-Instalar {
    if ($Semilla) {
        "== semilla (primera instalacion en esta consola)"
        pwsh -NoProfile -File (Join-Path $fase0 'semilla.ps1') | Select-Object -Last 1
        Portal instalar -Host_ $Host_ -Paquete (Join-Path $Build 'semilla\WiiCompiled-SuperSmashBrosBrawl_0.1.0.0_x64-semilla.msix') |
            Select-Object -Last 1
    }
    "== instalar $Version"
    $r = Portal instalar -Host_ $Host_ -Paquete $msix
    $r | Select-Object -Last 1
    # El portal informa del resultado DENTRO de la respuesta: hay que leerlo, no fiarse del POST.
    if (($r -join ' ') -notmatch '"Success"\s*:\s*true') { throw 'la instalacion no termino bien' }
}

function Paso-Config {
    "== Config.toml a \LocalState\WiiCompiled"
    Portal carpeta -Host_ $Host_ -Pfn $pfn -Ruta '\LocalState' -Nombre 'WiiCompiled' | Out-Null
    Portal subir -Host_ $Host_ -Pfn $pfn -Ruta '\LocalState\WiiCompiled' `
        -Archivo (Join-Path (Split-Path $xbox -Parent) 'package\Config.toml') | Select-Object -Last 1
}

function Paso-Disco {
    "== disco extraido a \LocalState\GameAssets\DATA (6,7 GB)"
    Portal carpeta -Host_ $Host_ -Pfn $pfn -Ruta '\LocalState' -Nombre 'GameAssets' | Out-Null
    Portal carpeta -Host_ $Host_ -Pfn $pfn -Ruta '\LocalState\GameAssets' -Nombre 'DATA' | Out-Null
    if (-not $Disco) { throw 'el paso "disco" necesita -Disco <carpeta DATA del disco extraido>' }
    pwsh -NoProfile -File (Join-Path $fase0 'subir_disco.ps1') -Host_ $Host_ -Pfn $pfn -Origen $Disco
}

function Paso-Lanzar {
    "== lanzar"
    foreach ($i in 1..3) {
        $r = Portal lanzar -Host_ $Host_ -Pfn $pfn -AppId $appid | Select-Object -Last 1
        if ($r -notmatch 'BadRequest') { "   lanzado (intento $i)"; break }
        "   intento $i rechazado (-2147023880), se reintenta"
    }
    New-Item -ItemType Directory -Force -Path $capturas | Out-Null
    Start-Sleep -Seconds 40
    $salida = Join-Path $capturas ("despliegue-{0}.png" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    # La captura vuelve vacia mientras la pantalla esta en transicion: se reintenta.
    foreach ($i in 1..3) {
        try { Portal captura -Host_ $Host_ -Salida $salida | Select-Object -Last 1; break }
        catch { "   captura vacia (intento $i), se reintenta" ; Start-Sleep -Seconds 5 }
    }
}

switch ($Paso) {
    'instalar' { Paso-Instalar }
    'config' { Paso-Config }
    'disco' { Paso-Disco }
    'lanzar' { Paso-Lanzar }
    'todo' { Paso-Instalar; Paso-Config; Paso-Disco; Paso-Lanzar }
}
