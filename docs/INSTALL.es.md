# Compilarlo e instalarlo, paso a paso

*(English: [INSTALL.md](INSTALL.md))*

Todo esto se hizo en **una Xbox Series X** en modo desarrollador. En una Series S no se ha probado
nunca; mira el aviso del [README](../README.es.md).

## 0. Antes de nada: la compilación de PC tiene que funcionar

Este repositorio porta **el resultado** de BrawlRecompiled, así que primero hay que tenerlo
compilando y corriendo en el PC, siguiendo *sus* instrucciones. Necesitas su producto `Play\`
funcionando antes de portar nada. Dos cosas que su README se deja y cuestan tiempo:

- `extract_wbfs.py` **solo acepta `.wbfs`**. Un `.iso` hay que convertirlo antes.
- **El traductor no viene compilado**: `dotnet build wiicompiled/translator/Translator.sln -c Release`.

El disco es *Super Smash Bros. Brawl* `RSBE01` **revisión 1**, y el manifiesto quiere un
`main_translate.dol` que **no** es el `main.dol` del disco: es ese más los módulos residentes, que
arma `tools/build_modules.py`. Extraer el disco no basta.

## 1. Las credenciales del Device Portal

Los scripts de despliegue hablan con la consola por el Device Portal, con autenticación Basic.
Leen el usuario y la contraseña de un archivo **fuera de este repositorio**:

```
%LOCALAPPDATA%\xbox-devportal\credenciales.txt
```

Una sola línea, `usuario:contraseña`, tal como los muestra la consola en **Configuración →
Configuración para desarrolladores** al activar el acceso remoto. Se crea a mano:

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\xbox-devportal" | Out-Null
Set-Content "$env:LOCALAPPDATA\xbox-devportal\credenciales.txt" 'tuusuario:tucontrasena' -NoNewline
```

⚠ **Esas credenciales no van nunca en un script, ni en un commit, ni en una issue.** Son la llave
de tu consola en tu red. El `.gitignore` bloquea `credenciales.txt`, pero la protección de verdad
es no escribirlas en ningún otro sitio.

## 2. El entorno

```powershell
$env:BRAWL_WIICOMPILED     = 'D:\brawl\wiicompiled'
$env:BRAWL_LLVM_MINGW      = 'D:\brawl\toolchain\llvm-mingw'
$env:BRAWL_UWP_DEP         = 'D:\uwp-dep'            # worleydl/uwp-dep, rama dawn-dev
$env:BRAWL_PLAY            = 'D:\brawl\Play'
$env:BRAWL_CERT_THUMBPRINT = '<la SHA-1 de tu certificado de firma>'
```

El certificado es tuyo. Su **CN tiene que coincidir** con el `Publisher` del
`package/Package.appxmanifest`: el hash de la familia del paquete sale de ese `Publisher`, así que
si no casan, no instala. O cambias el `Publisher` del manifiesto por tu CN, o haces un certificado
con el CN que hay puesto.

```powershell
New-SelfSignedCertificate -Type Custom -Subject 'CN=TuNombre' -KeyUsage DigitalSignature `
  -CertStoreLocation 'Cert:\CurrentUser\My' -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3')
```

La consola tiene que confiar en él: exporta la parte **pública** (`.cer`, nunca el `.pfx`) e
instálala en la Xbox con `tools\xbox-portal.ps1 certificado`.

## 3. Compilar

```powershell
tools\compilar.ps1 -Paso todo -Wiicompiled $env:BRAWL_WIICOMPILED -Build D:\brawl-uwp
```

Los pasos, si los quieres de uno en uno: `overlay`, `parchar`, `compdb`, `compilar`, `enlazar`,
`semilla`, `empaquetar`.

⚠ **`parchar` no es idempotente. Solo se corre sobre un overlay limpio.** La receta trae pares de
parches en cascada: uno mete un bloque provisional dentro de una función y el siguiente lo
sustituye por la llamada limpia. Aplicado dos veces, el provisional vuelve a entrar, el bloque
queda duplicado y sale `expected unqualified-id` — una linkage specification no puede ir dentro de
una función. El paso `overlay` rehace el árbol con `robocopy /E /IS /IT` justo para que `parchar`
reciba uno limpio.

La compilación son ~1.250 unidades. El enlace produce un único `SuperSmashBrosBrawl.exe` de unos
176 MB: al contrario que en PC, el juego va dentro del ejecutable y no en un `engine_usa.dll`.

## 4. Instalar en la consola

```powershell
tools\desplegar.ps1 -Paso instalar -Host_ <IP> -Build D:\brawl-uwp -Semilla
```

**`-Semilla` importa en la primera instalación de esta familia de paquetes.** El primer paquete de
una familia va a `D:\DevelopmentFiles`, que son unos 5 GB y suele estar lleno, y sale
«There is not enough space on the disk» aunque la consola parezca vacía. La semilla es un paquete
mínimo con la misma identidad en la versión 0.1.0.0: registra la familia, y el paquete bueno entra
después **como actualización**, que se coloca en otro sitio. En las siguientes instalaciones,
quita `-Semilla`.

## 5. Subir el disco

El juego lee sus datos de `LocalState\GameAssets\DATA`, no de dentro del paquete: son 6,7 GB que
sobreviven a reinstalarlo.

```powershell
tools\desplegar.ps1 -Paso disco -Host_ <IP> -Build D:\brawl-uwp -Disco D:\brawl\Disc\DATA
```

Dos topes duros de la consola, y no son el mismo:

- **El almacenamiento de desarrollo es una partición fija de ~30 GB** que comparten todos los
  paquetes de desarrollo. Nada que ver con los 800 GB de juegos. Cuando se llena, el portal
  contesta «There is not enough space on the disk» a *todo*, hasta a un archivo de 4 KB. Para
  hacer sitio sin perder partidas: `tools\xbox-vaciar-carpeta.ps1`. **Mira primero la carpeta
  `Logs` del propio port**: la nuestra tenía 480 MB de volcados por sesión.
- **El portal no extrae un ZIP de más de ~128 MB**, y aun así responde `OK`. Los lotes se cortan
  en 100 MB y lo que pase de ahí sube sin extraer.

⚠ **La subida se verifica sola al terminar**, con `auditar_disco.ps1`. No te lo saltes. Lo
aprendimos por las malas: una subida cortada por la partición llena dejó fuera 223 de los 314
`.brstm` de música, y el juego se instaló, arrancó y se jugó una partida entera **sin música de
fondo**, sin un solo error en ningún sitio. Si informa de archivos que faltan, libera espacio y
repite con `-Lista <el informe que ha escrito>`.

## 6. Configurar y lanzar

```powershell
tools\desplegar.ps1 -Paso config -Host_ <IP> -Build D:\brawl-uwp
tools\desplegar.ps1 -Paso lanzar -Host_ <IP> -Build D:\brawl-uwp
```

El `Config.toml` va a `LocalState\WiiCompiled\`. El `dvd_root = "../GameAssets/DATA"` es lo que
apunta el runtime al disco.

Lanzar por el portal falla de vez en cuando con `-2147023880` y al segundo intento va; el script
reintenta. La captura vuelve vacía mientras la pantalla está en transición: también reintenta.

## 7. La primera partida: los shaders

La primera vez que aparece cada personaje, escenario y efecto, Aurora traduce su configuración del
TEV a un shader y Dawn lo compila. Verás bajar los FPS. **Es normal y se cura solo**: cada pipeline
se guarda en `LocalState\WiiCompiled\Cache\pipeline_cache.db` y se reconstruye en bloque en el
siguiente arranque.

Para saltarse esa primera partida áspera, arma una semilla con sesiones ya jugadas:

```powershell
python tools\semilla_pipelines.py
```

Fusiona la caché de la consola con la del PC —son portables entre máquinas— y deja
`package/initial_pipeline_cache.db`, que `empaquetar_uwp.py` mete dentro del paquete.

⚠ **No uses el `initial_pipeline_cache.db` que trae WiiCompiled.** El CMake lo copia para sus
cuatro proyectos, pero su contenido es de New Super Mario Bros. Wii: medido aquí, comparte **1
pipeline de 393** con Brawl. Compilaría 1.155 shaders que este juego no pide, alargando el arranque
sin quitar ni un tirón.
