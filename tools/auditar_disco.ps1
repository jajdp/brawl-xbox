<#
.SYNOPSIS
  Compara el disco extraido del PC con lo que hay DE VERDAD en el LocalState de la Xbox.

.DESCRIPTION
  Por que existe: el 2026-11-02 el juego se quedo sin musica de fondo en la consola. De los 314
  `.brstm` de `files\sound\strm` solo habian subido 91, cortados limpiamente en orden alfabetico
  (de `H06.brstm` en adelante, nada). La causa de fondo: **el almacenamiento de desarrollo se
  lleno** y el portal empezo a contestar «There is not enough space on the disk». Nadie se entero
  porque la subida no comprobaba el resultado.

  Esta herramienta recorre las dos partes y dice, carpeta por carpeta, cuantos archivos y cuantos
  MB faltan. Escribe la lista de rutas que faltan en un .txt que `subir_disco.ps1 -Lista` come
  directamente, asi que reparar es: auditar -> subir -> auditar.

  Usa el API JSON del portal (`/api/filesystem/apps/files`), no el listado en tabla: parsear la
  tabla de texto da falsos positivos con los nombres largos.

  ⚠ Dos cosas que conviene saber del portal:
    - **No sobrescribe.** Si se vuelve a subir un archivo que ya existe, crea `nombre_0.ext`,
      `nombre_1.ext`… Por eso no hay que resubir a ciegas: duplica y gasta el espacio que falta.
    - Hay un tope de ~128 MB para el ZIP que extrae, aparte del espacio libre. Ver subir_disco.ps1.

.PARAMETER Excluir
  Patrones que NO cuentan como falta. Por defecto los dos `dummy*.dat` (381 MB), que son relleno
  de alineacion del disco de Wii y el juego no los abre nunca.

.EXAMPLE
  pwsh -File auditar_disco.ps1
  pwsh -File auditar_disco.ps1 -Informe C:\tmp\faltan.txt
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Host_,
    [int]$Puerto = 11443,
    [string]$Pfn = 'WiiCompiled-SuperSmashBrosBrawl_0.1.0.3_x64__mk2h16as9zg4e',
    [Parameter(Mandatory = $true)][string]$Origen,
    [string]$Destino = '\LocalState\GameAssets\DATA',
    [string[]]$Excluir = @('dummy1.dat', 'dummy2.dat'),
    [string]$Informe
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http

$base = "https://${Host_}:$Puerto"
$auth = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(
    (Get-Content -LiteralPath "$env:LOCALAPPDATA\xbox-devportal\credenciales.txt" -Raw).Trim()))
$h = [System.Net.Http.HttpClientHandler]::new()
$h.ServerCertificateCustomValidationCallback = [System.Net.Http.HttpClientHandler]::DangerousAcceptAnyServerCertificateValidator
$h.UseCookies = $false
$cliente = [System.Net.Http.HttpClient]::new($h)
$cliente.Timeout = [TimeSpan]::FromMinutes(10)
$cliente.DefaultRequestHeaders.Add('Authorization', $auth)

function Contenido([string]$ruta) {
    $url = "$base/api/filesystem/apps/files?knownfolderid=LocalAppData" +
           "&packagefullname=$Pfn&path=$([Uri]::EscapeDataString($ruta))"
    try {
        $r = $cliente.GetAsync($url).Result
        if (-not $r.IsSuccessStatusCode) { return @() }
        return @(($r.Content.ReadAsStringAsync().Result | ConvertFrom-Json).Items)
    } catch { return @() }
}

$carpetas = @('') + (Get-ChildItem -LiteralPath $Origen -Recurse -Directory |
    ForEach-Object { $_.FullName.Substring($Origen.Length + 1) })
"{0} carpetas que revisar en {1}" -f $carpetas.Count, $Origen

$faltan = [System.Collections.Generic.List[object]]::new()
$resumen = [System.Collections.Generic.List[object]]::new()

foreach ($rel in $carpetas) {
    $local = if ($rel) { Join-Path $Origen $rel } else { $Origen }
    $aqui = @(Get-ChildItem -LiteralPath $local -File | Where-Object {
        $nombre = $_.Name
        -not ($Excluir | Where-Object { $nombre -like $_ })
    })
    if ($aqui.Count -eq 0) { continue }

    $remoto = if ($rel) { $Destino + '\' + $rel } else { $Destino }
    $alla = @{}
    foreach ($i in (Contenido $remoto)) {
        if ($i.Type -eq 32) { $alla[$i.Name] = [long]$i.FileSize }
    }

    # Falta si no esta, o si esta con otro tamano (subida cortada a medias)
    $perdidos = @($aqui | Where-Object {
        -not $alla.ContainsKey($_.Name) -or $alla[$_.Name] -ne $_.Length
    })
    if ($perdidos.Count) {
        $resumen.Add([pscustomobject]@{
            Carpeta = if ($rel) { $rel } else { '(raiz)' }
            Hay     = $aqui.Count - $perdidos.Count
            Faltan  = $perdidos.Count
            MB      = [math]::Round((($perdidos | Measure-Object -Property Length -Sum).Sum / 1MB), 1)
        })
        foreach ($p in $perdidos) { $faltan.Add($p.FullName) }
    }
}

if ($resumen.Count -eq 0) {
    "`nDISCO COMPLETO: no falta nada (sin contar lo excluido: $($Excluir -join ', '))"
    exit 0
}

"`n=== carpetas incompletas ==="
$resumen | Sort-Object MB -Descending | Format-Table -AutoSize | Out-String -Width 160
$totalMb = ($resumen | Measure-Object -Property MB -Sum).Sum
"FALTAN {0} archivos, {1:N1} MB" -f $faltan.Count, $totalMb

if (-not $Informe) {
    $Informe = Join-Path $env:TEMP ("brawl-faltantes-{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
Set-Content -LiteralPath $Informe -Value $faltan -Encoding UTF8
"lista para reparar: $Informe"
"   pwsh -File subir_disco.ps1 -Lista `"$Informe`""
exit 1
