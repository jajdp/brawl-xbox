<#
.SYNOPSIS
  Envoltorio del Device Portal de la Xbox Series X (Dev Mode) para el lane Xbox de
  Recompilaciones: instalar paquetes, subir archivos a LocalState, lanzar, capturar.

.DESCRIPTION
  Mismo patrón que el lane Xbox de Decompilaciones (técnico de Ocarina of Time §4.4/§13.5):
  autenticación Basic con las credenciales del portal y token CSRF leído a mano del Set-Cookie (PowerShell no lo
  guarda porque el host es una IP), enviado como cabecera X-CSRF-Token y como cookie.
  Hay que correrlo con pwsh 7 (HttpClient con DangerousAcceptAnyServerCertificateValidator).

.EXAMPLE
  pwsh -File xbox-portal.ps1 paquetes
  pwsh -File xbox-portal.ps1 instalar -Paquete x.msix -Dependencias a.appx -Certificado x.cer
  pwsh -File xbox-portal.ps1 certificado -Certificado x.cer
  pwsh -File xbox-portal.ps1 lanzar -Pfn 'Familia_1.0.0.0_x64__hash' -AppId 'Familia_hash!App'
  pwsh -File xbox-portal.ps1 subir -Pfn ... -Ruta '\LocalState\WiiCompiled' -Archivo Config.toml
  pwsh -File xbox-portal.ps1 subir -Pfn ... -Ruta '\LocalState' -Archivo DATA.zip -Extraer
  pwsh -File xbox-portal.ps1 listar -Pfn ... -Ruta '\LocalState'
  pwsh -File xbox-portal.ps1 carpeta -Pfn ... -Ruta '\LocalState' -Nombre GameAssets
  pwsh -File xbox-portal.ps1 captura -Salida cap.png
  pwsh -File xbox-portal.ps1 procesos
  pwsh -File xbox-portal.ps1 parar -Pfn ... -AppId ...
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0, Mandatory = $true)]
  [ValidateSet('paquetes', 'instalar', 'certificado', 'estado', 'lanzar', 'parar', 'subir', 'listar', 'carpeta', 'borrar', 'descargar', 'captura', 'procesos', 'desinstalar')]
  [string]$Accion,
  [Parameter(Mandatory = $true)][string]$Host_,
  [int]$Puerto = 11443,
  [string]$Paquete,
  [string[]]$Dependencias = @(),
  [string]$Certificado,
  [string]$Pfn,
  [string]$AppId,
  [string]$Ruta,
  [string]$Archivo,
  [string]$Nombre,
  [string]$Salida,
  [switch]$Extraer
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http
$base = "https://${Host_}:$Puerto"
$auth = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes((Get-Content -LiteralPath "$env:LOCALAPPDATA\xbox-devportal\credenciales.txt" -Raw).Trim()))

function New-Cliente {
  $h = [System.Net.Http.HttpClientHandler]::new()
  $h.ServerCertificateCustomValidationCallback = [System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator
  $h.UseCookies = $false
  $c = [System.Net.Http.HttpClient]::new($h)
  $c.Timeout = [TimeSpan]::FromMinutes(60)
  $c.DefaultRequestHeaders.Add('Authorization', $auth)
  return $c
}

$cliente = New-Cliente
# Token CSRF: cualquier GET lo entrega en Set-Cookie
$r = $cliente.GetAsync("$base/api/app/packagemanager/packages").Result
$setCookie = ($r.Headers.GetValues('Set-Cookie') -join ',')
$tok = [regex]::Match($setCookie, 'CSRF-Token=([^;,\s]+)').Groups[1].Value
if (-not $tok) { throw "No llegó el CSRF-Token del portal ($($r.StatusCode))" }
$cliente.DefaultRequestHeaders.Add('X-CSRF-Token', $tok)
$cliente.DefaultRequestHeaders.Add('Cookie', "CSRF-Token=$tok")

function Get-Json([string]$url) {
  $resp = $cliente.GetAsync($url).Result
  $texto = $resp.Content.ReadAsStringAsync().Result
  if (-not $resp.IsSuccessStatusCode) { throw "GET $url -> $($resp.StatusCode): $texto" }
  return $texto | ConvertFrom-Json
}

function Send-Sin-Cuerpo([string]$metodo, [string]$url) {
  $req = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::new($metodo), $url)
  $resp = $cliente.SendAsync($req).Result
  $texto = $resp.Content.ReadAsStringAsync().Result
  Write-Host "$metodo $url -> $($resp.StatusCode) $texto"
  return $resp.IsSuccessStatusCode
}

function Send-Archivos([string]$url, [string[]]$rutas, [string]$campo) {
  $contenido = [System.Net.Http.MultipartFormDataContent]::new()
  $flujos = @()
  foreach ($ruta in $rutas) {
    $fs = [System.IO.File]::OpenRead($ruta)
    $flujos += $fs
    $sc = [System.Net.Http.StreamContent]::new($fs)
    $sc.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new('application/octet-stream')
    # El portal no entiende el Content-Disposition que .NET escribe por defecto (con filename*):
    # se fija a mano, con name y filename entre comillas y nada más.
    $cd = [System.Net.Http.Headers.ContentDispositionHeaderValue]::new('form-data')
    $cd.Name = '"' + $campo + '"'
    $cd.FileName = '"' + [System.IO.Path]::GetFileName($ruta) + '"'
    $sc.Headers.ContentDisposition = $cd
    $contenido.Add($sc)
  }
  $t0 = Get-Date
  $resp = $cliente.PostAsync($url, $contenido).Result
  $texto = $resp.Content.ReadAsStringAsync().Result
  foreach ($fs in $flujos) { $fs.Dispose() }
  $seg = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
  Write-Host "POST $url -> $($resp.StatusCode) en $seg s $texto"
  return $resp.IsSuccessStatusCode
}

function B64([string]$s) { return [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($s)) }
function Enc([string]$s) { return [Uri]::EscapeDataString($s) }

switch ($Accion) {
  'paquetes' {
    $p = Get-Json "$base/api/app/packagemanager/packages"
    $p.InstalledPackages | Where-Object { $_.Name -notlike 'Microsoft*' -and $_.Name } |
      Select-Object Name, PackageFullName, PackageRelativeId | Format-Table -AutoSize
  }
  'instalar' {
    if (-not $Paquete) { throw 'Falta -Paquete' }
    $archivos = @($Paquete) + $Dependencias
    if ($Certificado) { $archivos += $Certificado }
    $nombre = [System.IO.Path]::GetFileName($Paquete)
    $ok = Send-Archivos "$base/api/app/packagemanager/package?package=$(Enc $nombre)" $archivos 'package'
    if (-not $ok) { throw 'La instalación no fue aceptada' }
    for ($i = 0; $i -lt 120; $i++) {
      Start-Sleep -Seconds 2
      $resp = $cliente.GetAsync("$base/api/app/packagemanager/state").Result
      $texto = $resp.Content.ReadAsStringAsync().Result
      if ($resp.StatusCode -eq 'OK') { Write-Host "estado: $texto"; break }
      if ($i % 5 -eq 0) { Write-Host "  esperando... ($($resp.StatusCode))" }
    }
  }
  'certificado' {
    # Registra solo el certificado (.cer) del editor de un paquete. La consola en modo desarrollador
    # no lo exige y la pantalla Add del portal no tiene casilla para el: esta es la via manual.
    # El portal nombra el campo con el nombre del archivo, igual que hace su propio JavaScript.
    if (-not $Certificado) { throw 'Falta -Certificado' }
    $ok = Send-Archivos "$base/api/app/packagemanager/certificate" @($Certificado) ([System.IO.Path]::GetFileName($Certificado))
    if (-not $ok) { throw 'La consola no acepto el certificado' }
  }
  'estado' {
    $resp = $cliente.GetAsync("$base/api/app/packagemanager/state").Result
    Write-Host "$($resp.StatusCode) $($resp.Content.ReadAsStringAsync().Result)"
  }
  'lanzar' {
    if (-not $Pfn -or -not $AppId) { throw 'Faltan -Pfn y -AppId' }
    Send-Sin-Cuerpo 'POST' "$base/api/taskmanager/app?appid=$(B64 $AppId)&package=$(B64 $Pfn)" | Out-Null
  }
  'parar' {
    if (-not $Pfn -or -not $AppId) { throw 'Faltan -Pfn y -AppId' }
    Send-Sin-Cuerpo 'DELETE' "$base/api/taskmanager/app?appid=$(B64 $AppId)&package=$(B64 $Pfn)" | Out-Null
  }
  'subir' {
    if (-not $Pfn -or -not $Ruta -or -not $Archivo) { throw 'Faltan -Pfn, -Ruta y -Archivo' }
    $ext = if ($Extraer) { 'true' } else { 'false' }
    $url = "$base/api/filesystem/apps/file?knownfolderid=LocalAppData&packagefullname=$(Enc $Pfn)&path=$(Enc $Ruta)&extract=$ext"
    Send-Archivos $url @($Archivo) 'file' | Out-Null
  }
  'listar' {
    if (-not $Pfn -or -not $Ruta) { throw 'Faltan -Pfn y -Ruta' }
    $j = Get-Json "$base/api/filesystem/apps/files?knownfolderid=LocalAppData&packagefullname=$(Enc $Pfn)&path=$(Enc $Ruta)"
    $j.Items | Select-Object Name, Type, Size, DateCreated | Format-Table -AutoSize
  }
  'carpeta' {
    if (-not $Pfn -or -not $Ruta -or -not $Nombre) { throw 'Faltan -Pfn, -Ruta y -Nombre' }
    Send-Sin-Cuerpo 'POST' "$base/api/filesystem/apps/folder?knownfolderid=LocalAppData&packagefullname=$(Enc $Pfn)&path=$(Enc $Ruta)&newfoldername=$(Enc $Nombre)" | Out-Null
  }
  'borrar' {
    if (-not $Pfn -or -not $Ruta -or -not $Nombre) { throw 'Faltan -Pfn, -Ruta y -Nombre' }
    Send-Sin-Cuerpo 'DELETE' "$base/api/filesystem/apps/file?knownfolderid=LocalAppData&packagefullname=$(Enc $Pfn)&path=$(Enc $Ruta)&filename=$(Enc $Nombre)" | Out-Null
  }
  'descargar' {
    if (-not $Pfn -or -not $Ruta -or -not $Nombre) { throw 'Faltan -Pfn, -Ruta y -Nombre' }
    if (-not $Salida) { $Salida = $Nombre }
    $url = "$base/api/filesystem/apps/file?knownfolderid=LocalAppData&packagefullname=$(Enc $Pfn)&path=$(Enc $Ruta)&filename=$(Enc $Nombre)"
    $resp = $cliente.GetAsync($url).Result
    if (-not $resp.IsSuccessStatusCode) { throw "GET $url -> $($resp.StatusCode)" }
    $bytes = $resp.Content.ReadAsByteArrayAsync().Result
    [System.IO.File]::WriteAllBytes($Salida, $bytes)
    Write-Host "descargado: $Salida ($($bytes.Length) bytes)"
  }
  'captura' {
    if (-not $Salida) { $Salida = "captura-$(Get-Date -Format yyyyMMdd-HHmmss).png" }
    $bytes = $cliente.GetByteArrayAsync("$base/ext/screenshot?download=true").Result
    [System.IO.File]::WriteAllBytes($Salida, $bytes)
    Write-Host "captura: $Salida ($($bytes.Length) bytes)"
  }
  'procesos' {
    $j = Get-Json "$base/api/resourcemanager/processes"
    $j.Processes | Where-Object { $_.PackageFullName } | Select-Object ProcessId, ImageName, PackageFullName, IsRunning | Format-Table -AutoSize
  }
  'desinstalar' {
    if (-not $Pfn) { throw 'Falta -Pfn' }
    Send-Sin-Cuerpo 'DELETE' "$base/api/app/packagemanager/package?package=$(Enc $Pfn)" | Out-Null
  }
}
