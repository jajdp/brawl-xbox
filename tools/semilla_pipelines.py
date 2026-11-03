
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
# -*- coding: utf-8 -*-
r"""Arma la semilla de shaders del port: xbox\package\initial_pipeline_cache.db.

EL PROBLEMA
-----------
El Wii no tiene shaders: tiene el TEV, una unidad de combinacion de texturas que se configura
con registros. Aurora traduce cada combinacion que el juego usa a un shader WGSL y se lo pasa a
Dawn para que lo compile a HLSL y de ahi al binario de la GPU. Eso pasa la PRIMERA vez que un
material aparece en pantalla: un personaje nuevo, un escenario nuevo, un efecto nuevo. De ahi
los microtirones de la primera partida, que es el mismo fenomeno que el «shader compilation
stutter» de Dolphin.

No se congela, porque el runtime trae `skip_unready_pipelines` (activado por defecto, y tambien
en el menu de opciones como «Skip draws while shaders compile»): mientras el shader no esta
listo, ese dibujo se salta en vez de bloquear el hilo. Por eso se nota como una bajada de FPS y
no como un paron.

COMO SE ARREGLA SOLO
--------------------
Aurora guarda cada pipeline que construye en:

    \LocalState\WiiCompiled\Cache\pipeline_cache.db     descripciones GX, PORTABLES entre maquinas
    \LocalState\WiiCompiled\Cache\dawn_cache.db         el binario ya compilado, SOLO para esa GPU

Al arrancar recompila de una vez todo lo que haya en el primero (sin limite: lee todas las filas
que casen con su config_version, ordenadas por first_frame_used), asi que cada sesion arranca
sabiendose mas shaders que la anterior y los tirones se van apagando solos.

LO QUE HACE ESTE GUION
----------------------
Adelantar ese aprendizaje a la primera partida: fusiona varios pipeline_cache.db de partidas ya
jugadas en una semilla que viaja DENTRO del paquete, junto al exe, donde el runtime la busca con
SDL_GetBasePath(). Al arrancar, aurora la fusiona con la cache del jugador.

    python semilla_pipelines.py                        # PC + lo que haya en la consola
    python semilla_pipelines.py --sin-consola          # solo el PC
    python semilla_pipelines.py extra1.db extra2.db    # anade mas partidas

⚠ La semilla tiene que ser DE ESTE JUEGO. El repo trae una en runtime/assets/pipeline y el CMake
  la copia para los cuatro proyectos, pero es de New Super Mario Bros. Wii: medido el 2026-11-02,
  de los 393 pipelines que genero una partida de Brawl compartia exactamente UNO. Son 1.155
  shaders que Brawl no pide: alargan el arranque y no quitan ni un tiron.

⚠ Las filas llevan config_version. Aurora carga con `WHERE type = ? AND config_version = ?`, asi
  que una semilla hecha con otra version del runtime se ignora en silencio. El guion avisa.

No contiene codigo compilado ni datos del juego: son descripciones de pipeline. Es publicable.
"""
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

XBOX = Path(__file__).resolve().parent.parent
DESTINO = XBOX / "package" / "initial_pipeline_cache.db"

CACHE_PC = _ruta("BRAWL_PLAY", "el producto de PC") / "UserData" / "Cache" / "pipeline_cache.db"

PORTAL = Path(__file__).resolve().parent / "xbox-portal.ps1"
MAQUINA = _os.environ.get("BRAWL_XBOX_IP", "")  # IP de tu consola en modo desarrollador
PFN = _os.environ.get("BRAWL_PFN", "WiiCompiled-SuperSmashBrosBrawl_0.1.0.3_x64__mk2h16as9zg4e")
CACHE_CONSOLA = r"\LocalState\WiiCompiled\Cache"


def copiar_con_wal(origen: Path, destino: Path) -> bool:
    """El .db se lee con su -wal al lado: sqlite lo aplica al abrir. Sin el, faltan las
    ultimas partidas, que son justo las que interesan."""
    if not origen.is_file():
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)
    for sufijo in ("-wal", "-shm"):
        extra = origen.with_name(origen.name + sufijo)
        if extra.is_file():
            shutil.copy2(extra, destino.with_name(destino.name + sufijo))
    return True


def bajar_de_consola(trabajo: Path) -> Path | None:
    """Trae el pipeline_cache.db de la Xbox. Lo que se jugo en la consola es lo que mejor
    representa lo que un jugador vera ahi."""
    if not PORTAL.is_file():
        print(f"  sin {PORTAL.name}: me salto la consola")
        return None
    destino = trabajo / "consola.db"
    for nombre, local in (("pipeline_cache.db", destino),
                          ("pipeline_cache.db-wal", destino.with_name("consola.db-wal"))):
        orden = ["pwsh", "-NoProfile", "-File", str(PORTAL), "descargar", "-Host_", MAQUINA,
                 "-Pfn", PFN, "-Ruta", CACHE_CONSOLA, "-Nombre", nombre, "-Salida", str(local)]
        p = subprocess.run(orden, capture_output=True, text=True, errors="replace")
        if p.returncode != 0 and nombre.endswith(".db"):
            print(f"  no pude bajar {nombre}: {p.stderr.strip()[:160]}")
            return None
    return destino if destino.is_file() else None


def inventario(ruta: Path) -> dict:
    db = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True)
    try:
        filas = db.execute("SELECT type, config_version, COUNT(*) FROM pipeline_cache "
                           "GROUP BY type, config_version").fetchall()
    finally:
        db.close()
    return {(t, v): n for t, v, n in filas}


def main() -> int:
    extras = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    sin_consola = "--sin-consola" in sys.argv

    with tempfile.TemporaryDirectory(prefix="semilla-brawl-") as tmp:
        trabajo = Path(tmp)
        fuentes: list[tuple[str, Path]] = []

        if not sin_consola:
            print("== bajando la cache de la consola")
            c = bajar_de_consola(trabajo)
            if c:
                fuentes.append(("consola", c))
                print(f"  {c.stat().st_size // 1024} KiB")

        local = trabajo / "pc.db"
        if copiar_con_wal(CACHE_PC, local):
            fuentes.append(("PC", local))
        else:
            print(f"  sin cache de PC en {CACHE_PC}")

        for e in extras:
            d = trabajo / f"extra-{len(fuentes)}.db"
            if copiar_con_wal(e, d):
                fuentes.append((e.name, d))
            else:
                print(f"  no existe: {e}")

        if not fuentes:
            print("\nno hay ninguna cache que fusionar. Juega una partida primero: la cache se "
                  "escribe sola mientras se juega.")
            return 1

        print("\n== fuentes")
        versiones: dict[int, set] = {}
        for etiqueta, ruta in fuentes:
            inv = inventario(ruta)
            print(f"  {etiqueta:<10} {sum(inv.values()):>5} pipelines   {inv}")
            for (tipo, ver) in inv:
                versiones.setdefault(tipo, set()).add(ver)
        malas = {t: v for t, v in versiones.items() if len(v) > 1}
        if malas:
            print(f"\n⚠ config_version distintas para el mismo tipo: {malas}")
            print("  aurora solo precargara la que compile el binario; el resto es peso muerto.")
            print("  Suele pasar al mezclar caches de antes y despues de recompilar el runtime.")

        # La primera se clona entera (trae el esquema y la tabla aurora_schema).
        salida = trabajo / "semilla.db"
        base = sqlite3.connect(f"file:{fuentes[0][1].as_posix()}?mode=ro", uri=True)
        base.execute(f"VACUUM INTO '{salida.as_posix()}'")
        base.close()

        print("\n== fusion")
        db = sqlite3.connect(salida)
        print(f"  base {fuentes[0][0]}: {sum(inventario(salida).values())}")
        for etiqueta, ruta in fuentes[1:]:
            db.execute("ATTACH DATABASE ? AS otra", (str(ruta),))
            antes = db.execute("SELECT COUNT(*) FROM pipeline_cache").fetchone()[0]
            # Mismo upsert que aurora: ante un duplicado gana el first_frame_used menor, que es
            # el orden en que los recompila al arrancar.
            db.execute(
                "INSERT INTO pipeline_cache "
                "(type, hash, config_version, config_size, config, first_frame_used) "
                "SELECT type, hash, config_version, config_size, config, first_frame_used "
                "FROM otra.pipeline_cache WHERE true "
                "ON CONFLICT(type, hash) DO UPDATE SET "
                "first_frame_used = MIN(pipeline_cache.first_frame_used, excluded.first_frame_used)")
            db.commit()
            despues = db.execute("SELECT COUNT(*) FROM pipeline_cache").fetchone()[0]
            db.execute("DETACH DATABASE otra")
            print(f"  + {etiqueta}: +{despues - antes} nuevos")

        # Sin WAL: el archivo que viaja en el paquete tiene que valerse solo.
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("VACUUM")
        total = db.execute("SELECT COUNT(*) FROM pipeline_cache").fetchone()[0]
        db.close()

        DESTINO.parent.mkdir(parents=True, exist_ok=True)
        tmp_final = DESTINO.with_suffix(".db.tmp")
        shutil.copy2(salida, tmp_final)
        tmp_final.replace(DESTINO)

    print(f"\n{DESTINO}")
    print(f"  {total} pipelines, {DESTINO.stat().st_size // 1024} KiB")
    print("  empaquetar_uwp.py la mete junto al exe; al arrancar, el log debe decir\n"
          "  «Pipeline prewarm finished: N pipelines» con N cerca de ese numero.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
