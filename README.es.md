# Super Smash Bros. Brawl en Xbox — el port UWP

Cómo coger lo que **WiiCompiled** produce a partir de tu propio disco de *Super Smash Bros. Brawl*
—un ejecutable nativo, no un emulador— y hacerlo correr **en una Xbox Series X en modo
desarrollador**, como un paquete UWP que compilas y firmas tú.

*(English: [README.md](README.md))*

No es una teoría. El port arranca, dibuja, suena, lee el mando y reproduce los vídeos en la
consola a **60 FPS**, con sus partidas en el `LocalState` del paquete.

## En qué consola se probó

**En una Xbox Series X**, en modo desarrollador. Es el único hardware que cubre cualquier cosa
que se afirme aquí.

**En una Series S no se ha probado nunca, ni una vez.** Es otra máquina: menos memoria disponible
para el juego y una GPU más floja. Puede que funcione, puede que vaya más lenta o puede que ni
arranque; aquí no se ha medido nada en ella. Si lo ejecutas en una Series S, lo que obtengas no es
lo que cuenta este README, y ninguna de estas cifras es una promesa sobre esa consola.

## Qué es este repositorio

**La receta UWP entera**: los parches, la entrada UWP y las herramientas que compilan, enlazan,
empaquetan y despliegan. WiiCompiled compila para escritorio; esto es todo lo que hay que cambiar
para que el resultado viva dentro de un App Container de Xbox.

| Pieza | Qué es |
|---|---|
| `tools/parchar_uwp.py` | **53 parches sobre 20 archivos** — 46 en el runtime de WiiCompiled (GPL-3.0) y 7 en [Aurora](https://github.com/encounter/aurora) (MIT). Esto es el port |
| `src/uwp_main.cpp` | La entrada UWP: `SDL_RunApp` → el `main` del runtime |
| `src/compat/unistd.h` | Un puente de tres líneas para que zlib compile contra el ABI de MSVC |
| `tools/compile_check.py` | La pasada de compilación, dentro del entorno **store** de Visual Studio |
| `tools/enlazar_uwp.py` | El enlace, con `ld.lld`. Aquí viven las peores trampas del port |
| `tools/empaquetar_uwp.py` | El armado del paquete, `makeappx` y `signtool` |
| `tools/semilla.ps1` + `src/semilla.cpp` | El truco del **paquete semilla**, para cuando la primera instalación de una familia no cabe |
| `tools/subir_disco.ps1` + `auditar_disco.ps1` | Suben el disco extraído al `LocalState`, por lotes, **y comprueban después que llegó entero** |
| `tools/semilla_pipelines.py` | Arma la semilla de shaders, para que la primera partida no dé tirones |
| `tools/xbox-portal.ps1` | Un cliente del Device Portal: instalar, subir, listar, lanzar, captura |
| `package/` | El manifiesto, con `CHANGE-ME` donde va tu identidad, y el `Config.toml` del runtime |

## Qué no es

Aquí no hay **disco, ni ejecutable, ni `.msix`, ni mosaicos, ni semilla de shaders, ni ninguna de
las bibliotecas UWP** (Dawn, SDL3, `nod`, `libuwp`): son tuyos o son binarios de otros.
`package/Assets/` está vacía a propósito y [`docs/ASSETS.es.md`](docs/ASSETS.es.md) dice qué poner.

## Qué hace falta antes

| | |
|---|---|
| **BrawlRecompiled** | Hecho con la **0.5.3**. Compila tu disco a código nativo; sin él no hay nada que portar |
| **Tu propio disco** | *Super Smash Bros. Brawl* `RSBE01`, **revisión 1**. Ojo: su compilación quiere un `main_translate.dol` que **no** es el `main.dol` del disco; extraerlo no basta, mira las instrucciones del propio proyecto |
| **Visual Studio 2022** | Con el **componente C++ UWP**: hace falta su entorno `store` (`vcvarsall x64 store`), más `makeappx`/`signtool` del SDK de Windows |
| **El llvm-mingw de WiiCompiled** | clang con el ABI de MSVC, que es lo que compila y enlaza aquí |
| **El paquete UWP de dependencias** | [`worleydl/uwp-dep`](https://github.com/worleydl/uwp-dep), rama **`dawn-dev`**: Dawn, SDL3, `nod`, `dxcompiler` y `libuwp` ya compilados para UWP x64 |
| **Python 3**, **PowerShell 7** y **una Xbox en modo desarrollador** | Los scripts y la consola. Más un certificado de firma propio |

## Cómo va

```powershell
# Las rutas van en variables de entorno, no escritas en los scripts
$env:BRAWL_WIICOMPILED     = 'D:\brawl\wiicompiled'   # el arbol que compilaste para PC
$env:BRAWL_LLVM_MINGW      = 'D:\brawl\toolchain\llvm-mingw'
$env:BRAWL_UWP_DEP         = 'D:\uwp-dep'             # worleydl/uwp-dep, dawn-dev
$env:BRAWL_PLAY            = 'D:\brawl\Play'          # el producto de PC
$env:BRAWL_CERT_THUMBPRINT = '<la huella SHA-1 de tu certificado>'

# overlay + parchar + compilar + enlazar + empaquetar, de una vez
tools\compilar.ps1 -Paso todo -Wiicompiled $env:BRAWL_WIICOMPILED -Build D:\brawl-uwp

# instalar, subir el disco y lanzar
tools\desplegar.ps1 -Paso todo -Host_ <la IP de tu Xbox> -Build D:\brawl-uwp -Disco D:\brawl\Disc\DATA -Semilla
```

Paso a paso, incluida la parte de la consola: **[`docs/INSTALL.es.md`](docs/INSTALL.es.md)**.

## Qué hubo que resolver

El detalle está en **[`docs/HOW-IT-WORKS.es.md`](docs/HOW-IT-WORKS.es.md)**.

| | Síntoma | Arreglo |
|---|---|---|
| 1 | El disco se indexa en **0 archivos** y el juego muere en su primera lectura | `std::filesystem::relative()` devuelve vacío dentro de un App Container. Se usa `lexically_relative()` |
| 2 | `<filesystem>`, `<optional>` y `<algorithm>` salen vacíos en dos unidades | Salen de la base de compilación sin `-std=`. Con libc++ valía; contra la STL de MSVC, no |
| 3 | Siete APIs de Win32 no existen en la familia APP | `DWM_TIMING_INFO`, `IFileOpenDialog`, `MessageBoxW`, `CreateToolhelp32Snapshot`, `CreateProcessW`, `LoadLibraryExW` y Schannel, cada una apartada |
| 4 | El TLS no compila por ninguna de las dos ramas | Schannel no está en la familia APP y mbedTLS solo entra bajo `#ifndef _WIN32`. Hizo falta una **tercera** rama con stubs; Nintendo WFC cerró en 2014 |
| 5 | La primera instalación falla por «falta espacio» aunque la consola esté vacía | El primer paquete de una familia va a `D:\DevelopmentFiles`, 5 GB. Se instala antes una **semilla** mínima y el bueno encima, como actualización |
| 6 | El portal responde `OK` y no deja nada | No extrae un ZIP de más de ~128 MB. Los lotes se cortan y los archivos mayores suben sin extraer |
| 7 | El juego se juega, pero **sin música de fondo** | La subida del disco se había cortado por tener llena la partición de desarrollo y nadie se enteró. Ahora la subida **se verifica contra el origen** |
| 8 | Los shaders compilan en plena pelea y bajan los FPS | Es normal y se cura solo, pero una **semilla propia** deja limpia la primera partida. ⚠ La que trae WiiCompiled es de NSMBW: comparte **1 pipeline de 393** con Brawl |

## Créditos y licencia

Las herramientas y la receta son de **Recompilaciones**, bajo **[GPL-3.0](LICENSE)**, la misma
licencia que WiiCompiled, que es el código que modifican los 46 parches del runtime. Los otros 7
parchean [Aurora](https://github.com/encounter/aurora), que es MIT, © 2022 Luke Street, y MIT es
compatible con esta.

*Super Smash Bros. Brawl* es © Nintendo. WiiCompiled es de su autor, y
[BrawlRecompiled](https://github.com/josiahg2502-glitch/BrawlRecompiled) de JosiahG — **no se
reproduce ni una línea del proyecto contenedor**, solo de los árboles GPL-3.0 y MIT que lleva
dentro.

Este proyecto no está afiliado a ninguno de ellos, ni a Microsoft, y no distribuye nada que les
pertenezca: el detalle está en [`NOTICE.es.md`](NOTICE.es.md). Los titulares de derechos pueden
escribir a **jajdpmail@gmail.com**.
