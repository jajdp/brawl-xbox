# Cómo funciona el port, y qué hubo que resolver

*(English: [HOW-IT-WORKS.md](HOW-IT-WORKS.md))*

WiiCompiled recompila el código PowerPC de un disco de Wii a C++ nativo. Su producto es un
programa de Windows de escritorio. Una Xbox en modo desarrollador no ejecuta eso: ejecuta
**paquetes UWP dentro de un App Container**, una caja donde buena parte de Win32 sencillamente no
está.

Así que el port no es una reescritura. Son **53 parches sobre 20 archivos**, una entrada UWP y una
compilación con clang contra el ABI de MSVC en vez de la cadena de escritorio.

## La forma de la cosa

| | |
|---|---|
| Compilador | clang del llvm-mingw de WiiCompiled, `--target=x86_64-pc-windows-msvc`, con `-DWINAPI_FAMILY=WINAPI_FAMILY_APP`, dentro de `vcvarsall x64 store` |
| Enlazador | `ld.lld -flavor link /appcontainer /subsystem:windows,10.0` |
| Gráficos | Aurora sobre Dawn (WebGPU), de `worleydl/uwp-dep`, rama `dawn-dev` |
| Entrada | `src/uwp_main.cpp`: `SDL_RunApp` → el `main` del runtime |
| Resultado | ~1.250 unidades, un `.exe` de ~176 MB con el juego dentro |

La macro de la variante es **`MKW_UWP`**, y se queda así. Todo el runtime de WiiCompiled usa el
prefijo `MKW_` (`MKW_PPC_*`, `MKW_FLAT_GUEST_BASE`, `MKW_CRYPTOPP_ALLOW_CLANG_MSVC_ABI`), o sea
que es el prefijo del runtime y no el del juego. Renombrarlo solo separaría los parches de
upstream para nada.

## 1. El disco se indexa en cero archivos

El peor, porque parece un problema de empaquetado. El runtime recorre el directorio del disco y
arma su índice con:

```cpp
const fs::path relative = fs::relative(entry.path(), root, entryEc);
```

Dentro de un App Container, **`std::filesystem::relative()` devuelve una ruta vacía**. Sin
excepción y sin un código de error que mirar: el índice sale con cero entradas, el registro dice
`[dvd] disc index: 0 disc file(s)` y el juego muere en su primera lectura. El arreglo es
calcularlo léxicamente, que no toca el sistema de archivos:

```cpp
#if defined(MKW_UWP)
        const fs::path relative = entry.path().lexically_relative(root);
        if (relative.empty()) { return; }
#else
        const fs::path relative = fs::relative(entry.path(), root, entryEc);
        if (entryEc) { return; }
#endif
```

## 2. Dos unidades que compilan sin estándar

`host_platform.cpp` e `input_expr.cpp` salen de la base de compilación sin `-std=`, porque son de
targets propios. Contra libc++ el valor por defecto bastaba; contra la STL de MSVC significa que
`<filesystem>`, `<optional>` y `<algorithm>` salen **vacíos**, y aparece un muro de errores con
pinta de cabeceras que faltan. `compile_check.py` añade `-std=gnu++20` a toda unidad que llegue
sin uno.

## 3. Win32 que no existe en la familia APP

Siete sitios, cada uno apartado tras `#if !defined(MKW_UWP)`:

| Dónde | Qué |
|---|---|
| `hle/vi.cpp` | `DWM_TIMING_INFO` |
| `game_folder.cpp` | `IFileOpenDialog` y `shobjidl.h` — ya tenía un `#else` que devolvía true |
| `product/engine_loader.cpp` | `MessageBoxW` → `OutputDebugStringW`, y `LoadLibraryExW` → `LoadPackagedLibrary` |
| `hle/sampling_profiler.cpp` | `CreateToolhelp32Snapshot` |
| `netplay/netplay_lobby.cpp` | `CreateProcessW` |
| `product/engine_loader.cpp` | `cpuid.h` es una cabecera de GCC y choca con `intrin.h` bajo el ABI de MSVC: `__cpuid_count` reescrito con `__cpuidex` |
| `runtime_config.h` | `SHGetKnownFolderPath` — los datos van al `LocalState` del paquete |

## 4. El TLS necesitaba una tercera rama

`hle/net/network_ssl.cpp` tiene dos caminos y **no compila por ninguno**. Schannel (`CredHandle`,
`SCHANNEL_CRED`) no está en la familia APP, y los `#include <mbedtls/*>` solo entran bajo
`#ifndef _WIN32`. Se añadió una tercera rama con stubs que devuelven `SSL_ERR_FAILED`
(`ClearSslSession`, `SslHandshakeImpl`, `SslWrite`, `SslRead`). No se pierde nada: Nintendo WFC
cerró en 2014.

## 5. zlib contra el ABI de MSVC

`third_party/cryptopp/zdeflate.cpp` incluye `<unistd.h>`, que MSVC no tiene.
`src/compat/unistd.h` es un puente de tres líneas a `<io.h>` y `<process.h>`, añadido a la ruta de
inclusión solo para esas unidades.

## 6. La primera instalación no cabe

El primer paquete de una **familia** se coloca en `D:\DevelopmentFiles`, unos 5 GB y normalmente
llenos, y el portal responde «There is not enough space on the disk» aunque la consola parezca
vacía.

La salida es la **semilla**: un paquete mínimo con la misma identidad en la versión 0.1.0.0
(`src/semilla.cpp` es un `main` que no hace nada). Se instala eso primero; el paquete bueno entra
después **como actualización**, que va a otro sitio. `tools/semilla.ps1` lo arma y lo firma.

## 7. El portal miente con los ZIP grandes

`subir_disco.ps1` manda el disco en ZIP que la consola extrae. Medido el 2026-11-02 con 4,5 GB
libres: lotes de 117 MB y 122 MB entran; uno de 150 MB responde `InternalServerError`. El corte
anda por **128 MB**, así que los lotes se cortan en 100 MB y cualquier archivo más grande sube
**sin** extraer (en Brawl, los cuatro `.thp` grandes).

Y un tope distinto que es fácil confundir con ese: el almacenamiento de desarrollo es una
**partición fija de ~30 GB** para todos los paquetes de desarrollo de la consola, nada que ver con
los 800 GB de juegos.

## 8. El fallo mudo: un juego sin música

Este merece sección propia, porque no parecía un fallo.

Con la partición de desarrollo llena, la subida del disco se cortó a medias. El guion miraba la
respuesta de cada lote, así que no informó de ningún error en lo que mandó — pero **nunca informó
de lo que no llegó a mandar**. Resultado: 91 de los 314 `.brstm` entraron, cortados limpiamente en
orden alfabético. El paquete se instaló, el juego arrancó, fue a 60 FPS y se jugó una partida
entera. Solo que sin música de fondo, y sin que nada lo dijera: el juego pide el archivo de
stream, no está, y sigue tocando en silencio.

La lección está en `auditar_disco.ps1`, al que `subir_disco.ps1` llama ahora al terminar: **una
subida no está hecha cuando el portal dice OK, sino cuando se ha vuelto a leer el destino y cuadra
con el origen**, nombre y tamaño, archivo por archivo.

Dos cosas del portal que salieron de arreglarlo:

- **No sobrescribe.** Volver a subir un archivo que ya existe crea `nombre_0.ext`, `nombre_1.ext`…
  Así que resubirlo todo «por si acaso» duplica y se come justo el espacio que falta.
- El campo del tamaño en su JSON es **`FileSize`**, no `Size`. Leer el que no era hacía que
  `xbox-vaciar-carpeta.ps1` informara «0.0 MB» de cualquier carpeta, y por poco esconde los 480 MB
  de logs que eran el espacio más fácil de liberar.

## 9. Los shaders, y la semilla

La Wii no tiene shaders: tiene el **TEV**, que se configura con registros. Aurora traduce cada
combinación que el juego usa a WGSL, y Dawn la compila, la primera vez que ese material aparece en
pantalla. De ahí el tirón de la primera partida, el mismo fenómeno que el «shader compilation
stutter» de Dolphin.

No se congela porque `skip_unready_pipelines` viene activado (y está en el menú F10 como «Skip
draws while shaders compile»): mientras un pipeline no está listo, ese dibujo **se salta** en vez
de bloquear. Por eso se lee como una bajada de FPS y no como un parón.

Se cura solo porque hay dos cachés, y son cosas distintas:

| Archivo | Qué | Portable |
|---|---|---|
| `Cache/pipeline_cache.db` | **descripciones** de pipeline GX, sin código ni datos del juego | **sí**, entre máquinas, y entre PC y Xbox |
| `Cache/dawn_cache.db` | el blob que Dawn ya compiló | no, solo para esa GPU |

Al arrancar, Aurora reconstruye **todo** lo que haya en `pipeline_cache.db` —sin `LIMIT`, ordenado
por `first_frame_used`—, así que cada sesión empieza sabiendo más. Medido aquí: un arranque pasó
de precalentar 12 pipelines a **434 en 21,7 s** tras sembrarlo, y a 1.298 con el juego ya más
jugado.

`tools/semilla_pipelines.py` fusiona cachés de sesiones ya jugadas en una semilla que viaja dentro
del paquete. Tres trampas:

- **El `-wal` cuenta.** Copia el `.db` **con su `-wal` al lado** o pierdes justo las sesiones más
  recientes. Y al instalar uno en la consola: para la app, borra el `-wal` y el `-shm` viejos, y
  *entonces* sube — si no, SQLite le aplica el journal anterior encima del archivo nuevo.
- **`config_version`.** Aurora carga con `WHERE type = ? AND config_version = ?`; una semilla hecha
  con otra versión del runtime **se ignora en silencio**.
- **Tiene que ser de este juego.** La que trae WiiCompiled es de NSMBW: 1 pipeline compartido de
  393.
