<#
.SYNOPSIS
  Sube el disco extraido de Brawl al LocalState de la Xbox, en ZIP y por lotes de tamano acotado.

.DESCRIPTION
  Son 6,70 GB en 5.319 archivos: de uno en uno seria una peticion por archivo. El portal acepta un
  ZIP y lo extrae en la consola (extract=true), asi que se agrupa.

  ⚠⚠ **El portal NO extrae los ZIP grandes, y responde OK igual.** Medido el 2026-11-02: los lotes
  de 117 MB y 122 MB entraron enteros; los de 360 MB, 652 MB, 662 MB, 1.127 MB y 3.445 MB
  respondieron `OK` y no dejaron NADA en el destino. Ni error, ni aviso: la carpeta simplemente no
  aparece. Por eso aqui los lotes se cortan por tamano (-LoteMB, 100 por defecto) y al final se
  verifica cuantos archivos hay de verdad en la consola.

  Los ZIP se hacen SIN comprimir: los datos del juego ya vienen comprimidos (.pac, .brres, .thp),
  asi que comprimir no baja el tamano y si cuesta CPU.

.EXAMPLE
  pwsh -File subir_disco.ps1                      # todo
  pwsh -File subir_disco.ps1 -Solo 'files\sound'  # una carpeta
  pwsh -File subir_disco.ps1 -LoteMB 80
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Host_,
    # ⚠ El PFN lleva la VERSION dentro: si el paquete se actualiza y aqui se queda la vieja, el
    # portal responde InternalServerError a todo (el paquete que nombra ya no existe).
    [string]$Pfn = 'WiiCompiled-SuperSmashBrosBrawl_0.1.0.3_x64__mk2h16as9zg4e',
    [Parameter(Mandatory = $true)][string]$Origen,
    [string]$Trabajo = (Join-Path $env:TEMP 'brawl-subida'),
    [string]$Destino = '\LocalState\GameAssets\DATA',
    [int]$LoteMB = 100,
    [string[]]$Solo,
    # Archivo de texto con una ruta completa por linea: sube EXACTAMENTE esas y nada mas.
    # Es lo que produce auditar_disco.ps1 cuando una subida se queda corta.
    [string]$Lista,
    # Salta la comprobacion final contra el origen. No usar salvo para una prueba rapida.
    [switch]$SinVerificar
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$portal = Join-Path $PSScriptRoot 'xbox-portal.ps1'
$limite = $LoteMB * 1MB

# Que archivos entran
if ($Lista) {
    if (-not (Test-Path -LiteralPath $Lista)) { throw "no existe la lista: $Lista" }
    $archivos = Get-Content -LiteralPath $Lista | Where-Object { $_.Trim() } | ForEach-Object {
        $p = $_.Trim()
        if (-not (Test-Path -LiteralPath $p)) { Write-Warning "no existe: $p"; return }
        Get-Item -LiteralPath $p
    }
} else {
    $raices = if ($Solo) { $Solo } else { @('sys', 'files') }
    $archivos = foreach ($r in $raices) {
        $ruta = Join-Path $Origen $r
        if (-not (Test-Path -LiteralPath $ruta)) { Write-Warning "no existe: $ruta"; continue }
        $item = Get-Item -LiteralPath $ruta
        if ($item.PSIsContainer) { Get-ChildItem -LiteralPath $ruta -Recurse -File } else { $item }
    }
}
$archivos = @($archivos)
"{0:N0} archivos, {1:N2} GB, lotes de hasta {2} MB" -f $archivos.Count,
    (($archivos | Measure-Object -Property Length -Sum).Sum / 1GB), $LoteMB

New-Item -ItemType Directory -Force -Path $Trabajo | Out-Null
$lote = [System.Collections.Generic.List[object]]::new()
$peso = 0L
$n = 0
$subidos = 0

function Enviar-Lote($items, $indice) {
    if ($items.Count -eq 0) { return 0 }
    $zip = Join-Path $Trabajo ("lote{0:d3}.zip" -f $indice)
    if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force }
    $a = [System.IO.Compression.ZipFile]::Open($zip, 'Create')
    try {
        foreach ($f in $items) {
            $entrada = $f.FullName.Substring($Origen.Length + 1).Replace('\', '/')
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $a, $f.FullName, $entrada, [System.IO.Compression.CompressionLevel]::NoCompression)
        }
    } finally { $a.Dispose() }
    $mb = (Get-Item -LiteralPath $zip).Length / 1MB
    $t = Get-Date
    # ⚠ La respuesta del portal se MIRA. Silenciarla con Out-Null fue lo que me costo un rodeo
    # entero el 2026-11-02: con el almacenamiento lleno, cada lote contestaba
    # «InternalServerError … There is not enough space on the disk» y el guion seguia tan feliz;
    # el fallo solo aparecia despues, con el juego muriendo al pedir un archivo que no estaba.
    $respuesta = pwsh -NoProfile -File $portal subir -Host_ $Host_ -Pfn $Pfn -Ruta $Destino -Archivo $zip -Extraer 2>&1
    if ($respuesta -notmatch '->\s*OK') {
        Write-Host ("lote {0:d3}  FALLO: {1}" -f $indice, (($respuesta | Select-Object -Last 1) -replace '\s+', ' '))
        Remove-Item -LiteralPath $zip -Force
        throw "el portal rechazo el lote $indice; se para aqui para no dejar el disco a medias"
    }
    # Write-Host y no la salida normal: lo que una funcion escribe a la salida se DEVUELVE, y
    # entonces el contador de arriba recibe un array en vez de un numero.
    Write-Host ("lote {0:d3}  {1,5:N0} archivos  {2,7:N1} MB  {3,5:N1} s" -f $indice, $items.Count, $mb, ((Get-Date) - $t).TotalSeconds)
    Remove-Item -LiteralPath $zip -Force
    return $items.Count
}

# ⚠ El portal tiene DOS topes distintos, y conviene no confundirlos:
#   - el espacio libre del almacenamiento de desarrollo (30 GB fijos para todos los ports);
#   - y un tope de tamano para el ZIP que extrae. Medido el 2026-11-02 con 4,5 GB libres:
#     lotes de 117 y 122 MB entran, uno de 150 MB da InternalServerError. El corte anda por 128 MB.
# Un archivo que ya pase de ese tope no cabe en ningun ZIP, asi que se sube TAL CUAL (sin
# -Extraer) a su carpeta: el tope es de la extraccion, no de la subida. En Brawl son los cuatro
# videos mayores de movie\ (OPMovie.thp, 140 MB, es el de apertura y sin el el juego ni arranca).
$grandes = @($archivos | Where-Object { $_.Length -gt $limite })
$archivos = @($archivos | Where-Object { $_.Length -le $limite })
if ($grandes.Count) {
    "{0} archivo(s) pasan del lote y van sueltos, sin extraer" -f $grandes.Count
}

foreach ($f in $archivos) {
    if ($peso + $f.Length -gt $limite -and $lote.Count -gt 0) {
        $subidos += Enviar-Lote $lote (++$n)
        $lote.Clear(); $peso = 0
    }
    $lote.Add($f); $peso += $f.Length
}
$subidos += Enviar-Lote $lote (++$n)

foreach ($f in $grandes) {
    $rel = $f.FullName.Substring($Origen.Length + 1)
    $carpeta = $Destino + '\' + (Split-Path $rel -Parent)
    $t = Get-Date
    $r = pwsh -NoProfile -File $portal subir -Host_ $Host_ -Pfn $Pfn -Ruta $carpeta -Archivo $f.FullName 2>&1
    if ($r -notmatch '->\s*OK') {
        Write-Host ("suelto   {0,-24} FALLO: {1}" -f $f.Name, (($r | Select-Object -Last 1) -replace '\s+', ' '))
        throw "el portal rechazo $($f.Name)"
    }
    Write-Host ("suelto   {0,-24} {1,7:N1} MB  {2,5:N1} s" -f $f.Name, ($f.Length / 1MB), ((Get-Date) - $t).TotalSeconds)
    $subidos++
}

"TOTAL enviado: $subidos archivos en $n lotes"

# ⚠ ESTO NO ES ADORNO. Hasta el 2026-11-02 el guion terminaba aqui, diciendo «TOTAL enviado» y
# dando la cosa por buena. Ese dia la subida se corto por falta de espacio en la consola y se
# quedaron 223 de los 314 `.brstm` fuera; el juego se instalo, arranco y se jugo **sin musica de
# fondo**, y el fallo solo salio a la luz cuando el usuario lo noto jugando. El portal responde
# OK a lo que entra y el guion no puede saber lo que no envio: la unica prueba es volver a mirar.
if (-not $SinVerificar) {
    "`n== verificando contra el origen"
    $auditor = Join-Path $PSScriptRoot 'auditar_disco.ps1'
    if (Test-Path -LiteralPath $auditor) {
        pwsh -NoProfile -File $auditor -Host_ $Host_ -Pfn $Pfn -Origen $Origen -Destino $Destino
        if ($LASTEXITCODE -ne 0) {
            Write-Warning ("El disco NO quedo completo. Si fue por espacio, libera sitio y repite " +
                           "con -Lista sobre el informe de arriba. Para hacer hueco sin perder " +
                           "partidas: herramientas\xbox-vaciar-carpeta.ps1 (la carpeta Logs del " +
                           "propio port suele tener cientos de MB de volcados).")
            exit 1
        }
    } else {
        Write-Warning "no encuentro auditar_disco.ps1: la subida se queda SIN comprobar"
    }
}
