"""Fase 0 del lane Xbox de Super Smash Bros. Brawl: compile-check del árbol de Wiicompiled
con el ABI de MSVC (--target=x86_64-pc-windows-msvc) y las cabeceras de Windows en
modo UWP (WINAPI_FAMILY_APP), usando el clang 22 de llvm-mingw como compilador.

Toma las órdenes reales de la base de compilación mingw (compile_commands.json que
sale de `ninja -t compdb` en wiicompiled\\native-build), sustituye el
compilador y el target, quita lo que es exclusivo de esa base (PCH, dependencias .d)
y compila cada unidad por separado a un objeto en una carpeta temporal.

Hay que lanzarlo desde un entorno con INCLUDE y LIB del toolchain «store» de
Visual Studio (vcvarsall.bat x64 store): ver lanzar.cmd.

Uso:  python compile_check.py <compdb.json> <carpeta_salida> [--jobs N] [--solo runtime,generated,aurora]
"""
import collections
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
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

TOOLKIT = _ruta("BRAWL_LLVM_MINGW", "el llvm-mingw de WiiCompiled") / "bin"
CLANG = TOOLKIT / "clang.exe"
TARGET = "x86_64-pc-windows-msvc"
EXTRA = [
    f"--target={TARGET}",
    "-fms-compatibility-version=19.44",
    "-fms-runtime-lib=dll",
    "-DWINAPI_FAMILY=WINAPI_FAMILY_APP",
    "-D_WIN32_WINNT=0x0A00",
    "-D_CRT_SECURE_NO_WARNINGS",
    # cryptopp usa WINAPI_FAMILY_PARTITION() en config_os.h sin incluir antes winapifamily.h
    "-include", "winapifamily.h",
    # cryptopp trae una puerta propia de Wiicompiled para clang con ABI de MSVC
    "-DMKW_CRYPTOPP_ALLOW_CLANG_MSVC_ABI=1",
    "-ferror-limit=40",
    "-fno-color-diagnostics",
]
QUITAR_CON_ARG = {"-MT", "-MF", "-o"}
QUITAR = {"-MD", "-c", "-Winvalid-pch", "-pipe"}


UWP_DEP_INCLUDE = _ruta("BRAWL_UWP_DEP", "worleydl/uwp-dep, rama dawn-dev") / "x64" / "include"
# Cabeceras puente propias de este port (hoy solo el unistd.h para zlib).
COMPAT_INCLUDE = Path(__file__).resolve().parent.parent / "compat"
COPIAS_PCH = {}


def copia_sin_pch(ruta: str) -> str:
    """Copia la cabecera del PCH a la carpeta temporal (sin el .pch al lado)."""
    if ruta in COPIAS_PCH:
        return COPIAS_PCH[ruta]
    destino = Path(os.environ.get("TEMP", ".")) / "fase0-pch" / (str(abs(hash(ruta))) + "_" + Path(ruta).name)
    destino.parent.mkdir(parents=True, exist_ok=True)
    contenido = Path(ruta).read_text(encoding="utf-8", errors="replace")
    # La cabecera del PCH incluye por ruta ABSOLUTA las cabeceras de la base mingw: con el
    # overlay hay que apuntarlas a la copia de trabajo, o cada cabecera entra dos veces
    # (dos rutas distintas, mismo contenido) y todo el árbol falla por redefiniciones.
    contenido = con_overlay(contenido)
    destino.write_text(contenido, encoding="utf-8", newline="\n")
    COPIAS_PCH[ruta] = str(destino)
    return COPIAS_PCH[ruta]


def tokens(cmd: str):
    """Separa una línea de órdenes al estilo Windows: un token puede llevar trozos
    entre comillas pegados a texto sin comillas, como -I"H:/ruta con espacios"."""
    # Las comillas escapadas (\") son comillas de verdad para el compilador, por ejemplo en
    # -DIMGUI_USER_CONFIG=\"aurora/imgui_config.h\"; se preservan y se quitan las demás.
    marca = "\x01"
    cmd = cmd.replace('\\"', marca)
    return [t.replace('"', "").replace(marca, '"') for t in re.findall(r'(?:[^\s"]+|"[^"]*")+', cmd)]


def grupo(f: str):
    f = f.replace("\\", "/")
    if "/generated/" in f:
        return "generated"
    if "/runtime/third_party/" in f:
        return "third_party"
    if "/runtime/tests/" in f:
        return "tests"
    if "/runtime/" in f:
        return "runtime"
    if "/aurora-main/" in f:
        return "aurora"
    return "deps"


def limpiar_flags(toks):
    """Devuelve (flags, fuente) a partir de los tokens de una orden mingw."""
    flags = []
    fuente = None
    i = 1  # salta el compilador
    while i < len(toks):
        t = toks[i]
        if t in QUITAR_CON_ARG:
            i += 2
            continue
        if t in QUITAR:
            i += 1
            continue
        if t == "-Xclang" and i + 1 < len(toks):
            nxt = toks[i + 1]
            if nxt == "-include-pch":
                i += 4  # -Xclang -include-pch -Xclang <pch>
                continue
            if nxt == "-include" and i + 3 < len(toks) and toks[i + 2] == "-Xclang":
                # Es la cabecera del PCH de la base mingw. Si se incluye desde su sitio,
                # clang usa solo el .pch que tiene al lado (compilado para mingw) y falla:
                # se incluye una copia sin .pch al lado.
                flags += ["-include", copia_sin_pch(toks[i + 3])]
                i += 4
                continue
            i += 1
            continue
        if t.startswith("-O"):
            flags.append("-O1")
            i += 1
            continue
        if not t.startswith("-") and (t.endswith((".cpp", ".c", ".cc", ".cxx", ".S", ".s")) and os.path.exists(t)):
            fuente = t
            i += 1
            continue
        flags.append(t)
        i += 1
    return flags, fuente


def expandir_unity(entrada, flags):
    """Un unity .cxx se convierte en un trabajo por cada .cpp que incluye."""
    trabajos = []
    try:
        texto = Path(entrada).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return trabajos
    for m in re.finditer(r'#include\s+"([^"]+)"', texto):
        ruta = m.group(1)
        if os.path.exists(ruta):
            trabajos.append((ruta, flags))
    return trabajos


BUILDWORKSPACE = str(_ruta("BRAWL_WIICOMPILED", "el arbol de WiiCompiled")).replace("\\", "/")
OVERLAY = None  # carpeta con copias parcheadas de runtime/, aurora-main/ y projects/ (opción --overlay=)


def con_overlay(texto: str) -> str:
    """Redirige rutas de runtime/, aurora-main/ y projects/ de la base mingw a la copia de trabajo."""
    if not OVERLAY:
        return texto
    t = texto.replace("\\", "/")
    for sub in ("runtime", "aurora-main", "projects"):
        t = t.replace(f"{BUILDWORKSPACE}/{sub}", f"{OVERLAY}/{sub}")
    return t


def compilar(job, salida: Path):
    fuente, flags = job
    if OVERLAY:
        fuente = con_overlay(fuente)
        # Vulkan no existe en la consola y los stubs de DirectX de la base mingw sobran con el SDK real
        flags = [con_overlay(f) for f in flags
                 if f != "-DDAWN_ENABLE_BACKEND_VULKAN" and "aurora_dx_stubs" not in f]
    nombre = re.sub(r"[^A-Za-z0-9_.-]", "_", fuente.replace("\\", "/").split("/BuildWorkspace/")[-1])
    obj = salida / (nombre + ".obj")
    es_c = fuente.endswith(".c")
    es_asm = fuente.endswith((".S", ".s"))
    # Flags extra por archivo (dependencias que traen su propio soporte de UWP tras un define)
    extra_archivo = []
    nombre_fuente = fuente.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if nombre_fuente == "sqlite3.c":
        extra_archivo += ["-DSQLITE_OS_WINRT=1", "-DSQLITE_WIN32_FILEMAPPING_API=1"]
    # zlib: el zconf.h que CMake genero con llvm-mingw deja Z_HAVE_UNISTD_H activo y hace
    # #include <unistd.h>, que con el ABI de MSVC no existe. Se le pone delante el puente de
    # xbox/compat, que reexporta io.h (read/write/close/lseek, lo unico que zlib usa de POSIX).
    if "/dependencies/zlib/" in fuente.replace("\\", "/").lower():
        extra_archivo += ["-I" + str(COMPAT_INCLUDE)]
    cmd = [str(CLANG)]
    if not es_c and not es_asm:
        cmd.append("--driver-mode=g++")
    # Brawl: los targets propios (platform, input_expr) salen del compdb sin -std=. Con libc++
    # valia el default del compilador; contra la STL de MSVC, <filesystem>/<optional>/<algorithm>
    # quedan vacios y std::filesystem, std::optional y std::clamp dejan de existir. Se usa el
    # mismo estandar que el resto del arbol.
    if not es_c and not es_asm and not any(f.startswith("-std=") for f in flags):
        extra_archivo = extra_archivo + ["-std=gnu++20"]
    flags = flags + extra_archivo
    # Las cabeceras de SDL3/webgpu para UWP (uwp-dep) van ANTES que las de la base mingw:
    # el SDL3 oficial aborta con «Windows RT/UWP is no longer supported in SDL».
    cmd += EXTRA + ["-I" + str(UWP_DEP_INCLUDE)] + flags + ["-c", fuente, "-o", str(obj)]
    if es_asm:
        cmd = [str(CLANG)] + [f"--target={TARGET}"] + [f for f in flags if f.startswith(("-I", "-D"))] + ["-c", fuente, "-o", str(obj)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        rc, err = p.returncode, p.stderr
    except subprocess.TimeoutExpired:
        rc, err = -9, "TIMEOUT"
    errores = [l for l in err.splitlines() if " error: " in l or l.startswith("error:")]
    return {
        "fuente": fuente,
        "grupo": grupo(fuente),
        "rc": rc,
        "segundos": round(time.time() - t0, 1),
        "n_errores": len(errores),
        "errores": errores[:12],
        "stderr_bytes": len(err),
    }


def normaliza(msg: str):
    m = msg.split(" error: ", 1)[-1]
    m = re.sub(r"'[^']*'", "'…'", m)
    m = re.sub(r"\d+", "N", m)
    return m[:140]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__)
        return 2
    compdb, salida = Path(args[0]), Path(args[1])
    jobs_n = 24
    solo = None
    for a in sys.argv[1:]:
        if a.startswith("--jobs"):
            jobs_n = int(a.split("=", 1)[1] if "=" in a else sys.argv[sys.argv.index(a) + 1])
        if a.startswith("--solo="):
            solo = set(a.split("=", 1)[1].split(","))
        if a.startswith("--overlay="):
            global OVERLAY
            OVERLAY = a.split("=", 1)[1].replace("\\", "/").rstrip("/")
            EXTRA.append("-DMKW_UWP=1")
            EXTRA.append("-DAURORA_WINDOWS_STORE=1")
    salida.mkdir(parents=True, exist_ok=True)
    entradas = json.load(open(compdb, encoding="utf-8"))

    trabajos = []
    for e in entradas:
        f = e["file"]
        toks = tokens(e["command"])
        flags, fuente = limpiar_flags(toks)
        if fuente is None:
            continue
        if fuente.endswith(".cxx") and "/Unity/" in fuente.replace("\\", "/"):
            for ruta, fl in expandir_unity(fuente, flags):
                if grupo(ruta) != "deps":
                    trabajos.append((ruta, fl))
            continue
        if grupo(fuente) in ("deps",):
            # Las dependencias solo entran con --solo=deps, y nunca las que uwp-dep ya trae
            # compiladas para UWP (SDL3, libpng, zlib) ni libusb (adaptador GC: sin sentido en consola).
            f = fuente.replace("\\", "/").lower()
            if solo is None or "deps" not in solo:
                continue
            # tracy (perfilador) llama a GetUserNameExA, que no existe en la familia UWP, y no
            # se usa sin TRACY_ENABLE: fuera. Si el enlace lo reclama, se revisa.
            if any(x in f for x in ("/dependencies/sdl/", "/sdl-build/", "/png-build/", "/zlib-build/", "/libusb", "/tracy/")):
                continue
            if f.endswith("cmake_pch.hxx.cxx"):
                continue  # generadores de PCH de la base mingw: no son código
            if f.endswith("/builds/windows/ftsystem.c"):
                # El ftsystem de Win32 de freetype llama a CreateFileA; en UWP vale el genérico (stdio)
                fuente = fuente.replace("\\", "/").replace("/builds/windows/ftsystem.c", "/src/base/ftsystem.c")
        trabajos.append((fuente, flags))
    # sin duplicados
    vistos, unicos = set(), []
    for fuente, fl in trabajos:
        k = fuente.lower()
        if k not in vistos:
            vistos.add(k)
            unicos.append((fuente, fl))
    trabajos = [t for t in unicos if (solo is None or grupo(t[0]) in solo)]
    if OVERLAY:
        # El punto de entrada UWP se compila con los mismos flags que main.cpp del runtime
        for fuente, fl in unicos:
            if fuente.replace("\\", "/").endswith("runtime/src/main.cpp"):
                trabajos.append((f"{BUILDWORKSPACE}/runtime/src/uwp_main.cpp", fl))
                break
    print(f"unidades a compilar: {len(trabajos)}  (jobs={jobs_n})")
    por_grupo = collections.Counter(grupo(t[0]) for t in trabajos)
    print("  " + "  ".join(f"{k}={v}" for k, v in por_grupo.items()))
    sys.stdout.flush()

    t0 = time.time()
    resultados = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs_n) as ex:
        futs = [ex.submit(compilar, t, salida) for t in trabajos]
        for n, fu in enumerate(concurrent.futures.as_completed(futs), 1):
            r = fu.result()
            resultados.append(r)
            if n % 25 == 0 or r["rc"] != 0 and r["grupo"] in ("runtime", "generated"):
                ok = sum(1 for x in resultados if x["rc"] == 0)
                print(f"  [{n}/{len(trabajos)}] ok={ok} fail={n - ok}  ({time.time() - t0:.0f}s)")
                sys.stdout.flush()

    # resumen
    resumen = {}
    for g in sorted(por_grupo):
        rs = [r for r in resultados if r["grupo"] == g]
        resumen[g] = {"total": len(rs), "ok": sum(1 for r in rs if r["rc"] == 0), "fail": sum(1 for r in rs if r["rc"] != 0)}
    hist = collections.Counter()
    ejemplo = {}
    for r in resultados:
        for m in r["errores"]:
            k = normaliza(m)
            hist[k] += 1
            ejemplo.setdefault(k, r["fuente"].replace("\\", "/").split("/BuildWorkspace/")[-1])
    informe = {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "compilador": str(CLANG),
        "target": TARGET,
        "extra": EXTRA,
        "duracion_s": round(time.time() - t0, 1),
        "resumen": resumen,
        "histograma_errores": [{"mensaje": k, "veces": v, "ejemplo": ejemplo[k]} for k, v in hist.most_common(60)],
        "resultados": sorted(resultados, key=lambda r: (r["grupo"], r["rc"] == 0, r["fuente"])),
    }
    (salida / "informe.json").write_text(json.dumps(informe, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n=== RESUMEN ===")
    for g, s in resumen.items():
        print(f"  {g:12s} total={s['total']:4d}  ok={s['ok']:4d}  fail={s['fail']:4d}")
    print(f"  duración {informe['duracion_s']} s")
    print("=== errores más frecuentes ===")
    for h in informe["histograma_errores"][:25]:
        print(f"  {h['veces']:4d}  {h['mensaje']}   [{h['ejemplo']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
