"""Fase 1: arma el paquete .msix del port UWP de Super Smash Bros. Brawl y lo firma.

Uso:  python empaquetar_uwp.py <SuperSmashBrosBrawl.exe enlazado> <salida.msix> [carpeta_package]

`carpeta_package` (por defecto `xbox\\package`) aporta el `Package.appxmanifest` y los mosaicos
`Assets\\` que genera `generar_assets.py` a partir del arte del usuario.

En el PC, Brawl son DOS binarios: `SuperSmashBrosBrawl.exe` es solo el cargador (283 KB) y el
juego vive en `engine_usa.dll` (182,9 MB), que el cargador abre con `LoadLibraryExW`. Eso esta
pensado para elegir region (usa/pal) y variante de CPU (v2/v3) en caliente.

Aqui **no**: en la consola solo hace falta la region USA y una CPU, asi que se enlaza todo en un
unico `SuperSmashBrosBrawl.exe` de 176,6 MB (`enlazar_uwp.py` aparta `product_engine_loader.cpp`)
y la entrada es `uwp_main.cpp` -> `SDL_RunApp` -> `RuntimeMain`. Un binario menos que cargar y
ningun `LoadPackagedLibrary` de por medio.

Necesita makeappx.exe y signtool.exe del Windows SDK y un certificado de firma de codigo propio,
instalado en Cert:\\CurrentUser\\My. Su huella SHA-1 se pasa en la variable de entorno
BRAWL_CERT_THUMBPRINT, y su CN tiene que coincidir con el Publisher del Package.appxmanifest:
de ese Publisher sale el hash de la familia del paquete, asi que si no casan, no instala.

Lo que NO va dentro: los assets del juego (el disco extraido). Esos se suben una sola vez a
`LocalState\\GameAssets\\DATA` por el Device Portal y sobreviven a reinstalar el paquete, porque
es la misma familia. El `Config.toml` va aparte, en `LocalState\\WiiCompiled\\`.
"""
import shutil
import subprocess
import sys
from pathlib import Path

# --- Configuracion del entorno ------------------------------------------------------------
# Las rutas del arbol de trabajo NO van aqui escritas: cada quien tiene la suya. Se leen de
# variables de entorno, que se ponen una vez por sesion (ver README).
import os as _os


def _ruta(variable: str, para_que: str) -> Path:
    valor = _os.environ.get(variable)
    if not valor:
        raise SystemExit(
            f"Falta la variable de entorno {variable} ({para_que}).\n"
            f"  PowerShell:  $env:{variable} = 'D:\\ruta\\que\\sea'\n"
            f"  cmd:         set {variable}=D:\\ruta\\que\\sea")
    return Path(valor)
# ------------------------------------------------------------------------------------------

SDK_BIN = Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64")
MAKEAPPX = SDK_BIN / "makeappx.exe"
SIGNTOOL = SDK_BIN / "signtool.exe"
HUELLA = _os.environ.get("BRAWL_CERT_THUMBPRINT", "")  # huella SHA-1 de TU certificado

XBOX = Path(__file__).resolve().parent.parent          # ...\Super Smash Bros Brawl\xbox
PLAY_PC = _ruta("BRAWL_PLAY", "el producto de PC que genera WiiCompiled")
UWP_DEP_BIN = _ruta("BRAWL_UWP_DEP", "worleydl/uwp-dep, rama dawn-dev") / "x64" / "bin"

# libpng16.dll y z.dll NO estan en la rama dawn-dev del depot: en este port zlib y libpng se
# enlazan desde los objetos del propio arbol (ver enlazar_uwp.py), asi que no hacen falta aqui.
DLLS = ["SDL3.dll", "webgpu_dawn.dll", "nod.dll", "dxcompiler.dll", "dxil.dll", "libuwp.dll"]

# Lo que el runtime lee junto al ejecutable, copiado del producto de PC.
RECURSOS = ["dsp_coef.bin"]
CARPETAS = ["wii_bootstrap"]

# initial_pipeline_cache.db: la semilla de shaders, y va junto al exe DENTRO del paquete.
#
# Aurora traduce cada material del Wii (TEV) a un shader WGSL la primera vez que aparece, y
# compilarlo cuesta. Lo guarda en \LocalState\WiiCompiled\Cache\pipeline_cache.db y al arrancar
# recompila de golpe todo lo que haya ahi, asi que el juego se va puliendo solo; pero la PRIMERA
# partida de una instalacion nueva paga el precio en plena pelea. La semilla es ese .db ya hecho,
# que aurora fusiona con el del jugador al arrancar: la primera partida ya sale sin tirones.
#
# ⚠ Tiene que ser de ESTE juego. El repo trae una en runtime/assets/pipeline (1.156 pipelines) y
# el CMake la copia para los cuatro proyectos, pero es de NSMBW: medido el 2026-11-02, comparte
# UN pipeline con los 393 que genero Brawl. Ponerla equivaldria a compilar 1.155 shaders que
# Brawl nunca pide, alargando el arranque sin quitar un solo tiron. La de aqui se genera con
# fase0\semilla_pipelines.py a partir de partidas reales de Brawl.
SEMILLA_PIPELINES = "initial_pipeline_cache.db"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    exe = Path(sys.argv[1])
    salida = Path(sys.argv[2])
    paquete = Path(sys.argv[3]) if len(sys.argv) > 3 else (XBOX / "package")

    if not exe.is_file():
        print(f"no existe el ejecutable enlazado: {exe}")
        return 2
    # El exe lleva el juego dentro (176,6 MB): si llega uno del tamano del de PC (283 KB) es el
    # cargador, no el binario enlazado para UWP.
    if exe.stat().st_size < 50 * 1024 * 1024:
        print(f"⚠ el ejecutable solo pesa {exe.stat().st_size:,} bytes: parece el cargador de PC")
        print("  y no el binario UWP enlazado con todo dentro. Se sigue, pero revisalo.")

    raiz = salida.parent / "contenido"
    if raiz.exists():
        shutil.rmtree(raiz)  # carpeta de trabajo propia, regenerable
    raiz.mkdir(parents=True)

    shutil.copy2(exe, raiz / "SuperSmashBrosBrawl.exe")
    for d in DLLS:
        origen = UWP_DEP_BIN / d
        if not origen.is_file():
            print(f"falta en el depot: {origen}")
            return 2
        shutil.copy2(origen, raiz / d)
    for r in RECURSOS:
        shutil.copy2(PLAY_PC / r, raiz / r)
    for c in CARPETAS:
        shutil.copytree(PLAY_PC / c, raiz / c)
    # El runtime la busca por SDL_GetBasePath(), o sea la carpeta del exe dentro del paquete. Si
    # falta, el log lo dice al arrancar: «No bundled initial pipeline cache found at ...».
    semilla = paquete / SEMILLA_PIPELINES
    if semilla.is_file():
        shutil.copy2(semilla, raiz / SEMILLA_PIPELINES)
        print(f"semilla de shaders: {semilla.stat().st_size / 1048576:.1f} MB")
    else:
        print(f"⚠ sin {SEMILLA_PIPELINES}: la primera partida compilara shaders en plena pelea.")
        print(f"  generala con fase0\\semilla_pipelines.py y dejala en {paquete}")
    shutil.copytree(paquete / "Assets", raiz / "Assets")
    shutil.copy2(paquete / "Package.appxmanifest", raiz / "AppxManifest.xml")
    print(f"manifiesto: {paquete / 'Package.appxmanifest'}")
    archivos = [p for p in raiz.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in archivos)
    print(f"contenido: {len(archivos)} archivos, {total / 1048576:.1f} MB")

    if salida.exists():
        salida.unlink()
    p = subprocess.run([str(MAKEAPPX), "pack", "/o", "/d", str(raiz), "/p", str(salida)],
                       capture_output=True, text=True, errors="replace")
    print(p.stdout[-1500:], p.stderr[-1500:])
    if p.returncode != 0:
        # APPX3207 = algun mosaico pasa de 204.800 B. Con makeappx no suele saltar; si salta, se
        # cuantizan los PNG del arte o se empaqueta por MSBuild con
        # /p:AppxPackageValidationEnabled=false.
        return p.returncode
    p = subprocess.run([str(SIGNTOOL), "sign", "/fd", "SHA256", "/sha1", HUELLA, "/s", "My", str(salida)],
                       capture_output=True, text=True, errors="replace")
    print(p.stdout[-800:], p.stderr[-800:])
    if p.returncode == 0:
        print(f"OK: {salida} ({salida.stat().st_size:,} bytes)")
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
