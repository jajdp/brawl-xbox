<#
.SYNOPSIS
  Vacia una carpeta del LocalState de un paquete de la Xbox (Dev Mode), por el Device Portal.

.DESCRIPTION
  El espacio de desarrollo de la consola es una particion FIJA de 30 GB (medido desde dentro con
  GetDiskFreeSpaceExW: «libre 0 MiB de 30719 MiB»), independiente de los 802 GB del almacenamiento
  de juegos. Cuando se llena, el portal responde a cualquier escritura con
  «There is not enough space on the disk» (-2147024784), hasta para un archivo de 4 KB.

  Esta herramienta libera sitio sin desinstalar el paquete, para no perder las partidas: borra el
  contenido de UNA carpeta (p. ej. \LocalState\GameAssets) y deja el resto en pie.

  El portal no tiene borrado de carpetas: hay que quitar archivo por archivo y despues cada
  carpeta YA VACIA, de abajo arriba. Eso hace esta herramienta, con una sola conexion.

  ⚠ Por defecto NO borra: hace el recuento y lo enseña. Hay que pasar -Ejecutar.

.EXAMPLE
  pwsh -File xbox-vaciar-carpeta.ps1 -Pfn 'WiiCompiled-RetroRewind_0.1.0.0_x64__mk2h16as9zg4e' -Ruta '\LocalState\GameAssets'
  pwsh -File xbox-vaciar-carpeta.ps1 -Pfn '…' -Ruta '\LocalState\GameAssets' -Ejecutar
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Pfn,
    [Parameter(Mandatory = $true)][string]$Ruta,
    [Parameter(Mandatory = $true)][string]$Host_,
    [int]$Puerto = 11443,
    [switch]$Ejecutar
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http

$base = "https://${Host_}:$Puerto"
$auth = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(
    (Get-Content -LiteralPath "$env:LOCALAPPDATA\xbox-devportal\credenciales.txt" -Raw).Trim()))

$h = [System.Net.Http.HttpClientHandler]::new()
$h.ServerCertificateCustomValidationCallback = [System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator
$h.UseCookies = $false
$c = [System.Net.Http.HttpClient]::new($h)
$c.Timeout = [TimeSpan]::FromMinutes(10)
$c.DefaultRequestHeaders.Add('Authorization', $auth)
$r = $c.GetAsync("$base/api/app/packagemanager/packages").Result
$tok = [regex]::Match((($r.Headers.GetValues('Set-Cookie')) -join ','), 'CSRF-Token=([^;,\s]+)').Groups[1].Value
if (-not $tok) { throw "no llego el CSRF-Token ($($r.StatusCode))" }
$c.DefaultRequestHeaders.Add('X-CSRF-Token', $tok)
$c.DefaultRequestHeaders.Add('Cookie', "CSRF-Token=$tok")

function Enc([string]$s) { return [Uri]::EscapeDataString($s) }

function Listar([string]$ruta) {
    $url = "$base/api/filesystem/apps/files?knownfolderid=LocalAppData&packagefullname=$(Enc $Pfn)&path=$(Enc $ruta)"
    $resp = $c.GetAsync($url).Result
    if (-not $resp.IsSuccessStatusCode) { return @() }
    $j = $resp.Content.ReadAsStringAsync().Result | ConvertFrom-Json
    return @($j.Items)
}

# Recorrido en profundidad: primero los archivos, y las carpetas se apuntan para vaciarlas al final.
$archivos = [System.Collections.Generic.List[object]]::new()
$carpetas = [System.Collections.Generic.List[string]]::new()
$pila = [System.Collections.Generic.Stack[string]]::new()
$pila.Push($Ruta)
while ($pila.Count -gt 0) {
    $actual = $pila.Pop()
    foreach ($i in (Listar $actual)) {
        # Type 16 = carpeta, 32 = archivo (lo mismo que usa xbox-portal.ps1 al listar)
        if ($i.Type -eq 16) {
            $hijo = "$actual\$($i.Name)"
            $carpetas.Add($hijo)
            $pila.Push($hijo)
        } else {
            # ⚠ El campo del JSON del portal es FileSize, NO Size. Con $i.Size el recuento salia
            # «0.0 MB» SIEMPRE y parecia que la carpeta no ocupaba nada: el 2026-11-02 me hizo
            # dudar de si valia la pena vaciar los logs de Brawl, que eran 480 MB de verdad.
            $archivos.Add([pscustomobject]@{ Ruta = $actual; Nombre = $i.Name; Tam = [int64]$i.FileSize })
        }
    }
}

$mb = ($archivos | Measure-Object -Property Tam -Sum).Sum / 1MB
"carpeta  : $Ruta"
"paquete  : $Pfn"
"contenido: {0:N0} archivos en {1:N0} subcarpeta(s), {2:N1} MB" -f $archivos.Count, $carpetas.Count, $mb
if (-not $Ejecutar) {
    "`nSIMULACRO: no se ha borrado nada. Para hacerlo de verdad, repite con -Ejecutar."
    return
}

$t0 = Get-Date
$fallos = 0
$n = 0
foreach ($a in $archivos) {
    $url = "$base/api/filesystem/apps/file?knownfolderid=LocalAppData&packagefullname=$(Enc $Pfn)&path=$(Enc $a.Ruta)&filename=$(Enc $a.Nombre)"
    $req = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Delete, $url)
    $resp = $c.SendAsync($req).Result
    if (-not $resp.IsSuccessStatusCode) { $fallos++ }
    $n++
    if ($n % 250 -eq 0) { Write-Host ("  {0:N0}/{1:N0} archivos  ({2:N0} s)" -f $n, $archivos.Count, ((Get-Date) - $t0).TotalSeconds) }
}
# Las carpetas, de la mas profunda a la mas alta (ya vacias).
foreach ($carpeta in ($carpetas | Sort-Object -Property { ($_ -split '\\').Count } -Descending)) {
    $padre = Split-Path $carpeta -Parent
    $nombre = Split-Path $carpeta -Leaf
    $url = "$base/api/filesystem/apps/file?knownfolderid=LocalAppData&packagefullname=$(Enc $Pfn)&path=$(Enc $padre)&filename=$(Enc $nombre)"
    $req = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Delete, $url)
    [void]$c.SendAsync($req).Result
}
"borrados {0:N0} archivos en {1:N0} s; fallos: {2}" -f $archivos.Count, ((Get-Date) - $t0).TotalSeconds, $fallos
"comprobacion: quedan {0:N0} archivos" -f (@(Listar $Ruta).Count)
