"""Genera los mosaicos PNG que exige el manifiesto UWP a partir del arte del usuario.

El arte vive en `dependencias-usuario\\Display Images\\` y ya viene en las medidas buenas:

    xbox-sq1.png   150x150    el cuadrado pequeno
    xbox-sq2.png   300x300    el cuadrado grande (el cuadro en «Mis juegos y aplicaciones»)
    xbox-ss1.png   620x300    el ancho
    xbox-ss2.png  1240x600    la pantalla de carga

Ni un pixel del juego ni de su decompilacion: es la regla de la casa, y el arte es del usuario.

⚠ Dos cosas que cuestan un empaquetado fallido cada una:
  - Sin `resources.pri`, makeappx exige **tambien** el nombre sin calificador de escala, y ese
    archivo lleva el tamano de `scale-200` (`Square150x150Logo.png` mide 300x300).
  - Los PNG se guardan con `optimize=True`: por encima de 204.800 B, MSBuild corta el empaquetado
    con APPX3207. Las fuentes del usuario pasan de ese limite y al reescribirlas bajan de sobra.
"""
import sys
from pathlib import Path

from PIL import Image

BASE = Path(__file__).resolve().parent.parent.parent  # ...\Super Smash Bros Brawl
ARTE = BASE / "dependencias-usuario" / "Display Images"
SALIDA = BASE / "xbox" / "package" / "Assets"

# destino -> (medidas, archivo de origen)
TILES = {
    "Square44x44Logo.png": ((88, 88), "xbox-sq1.png"),
    "Square44x44Logo.scale-200.png": ((88, 88), "xbox-sq1.png"),
    "Square44x44Logo.targetsize-24_altform-unplated.png": ((24, 24), "xbox-sq1.png"),
    "Square150x150Logo.png": ((300, 300), "xbox-sq2.png"),
    "Square150x150Logo.scale-200.png": ((300, 300), "xbox-sq2.png"),
    "StoreLogo.png": ((50, 50), "xbox-sq1.png"),
    "StoreLogo.scale-200.png": ((100, 100), "xbox-sq1.png"),
    "LockScreenLogo.png": ((48, 48), "xbox-sq1.png"),
    "LockScreenLogo.scale-200.png": ((48, 48), "xbox-sq1.png"),
    "Wide310x150Logo.png": ((620, 300), "xbox-ss1.png"),
    "Wide310x150Logo.scale-200.png": ((620, 300), "xbox-ss1.png"),
    "SplashScreen.png": ((1240, 600), "xbox-ss2.png"),
    "SplashScreen.scale-200.png": ((1240, 600), "xbox-ss2.png"),
}

LIMITE_APPX = 204_800


def main() -> int:
    faltan = sorted({o for _, o in TILES.values() if not (ARTE / o).is_file()})
    if faltan:
        print("falta arte en " + str(ARTE))
        for f in faltan:
            print("   " + f)
        return 1

    SALIDA.mkdir(parents=True, exist_ok=True)
    cache = {}
    grandes = []
    for nombre, ((w, h), origen) in TILES.items():
        if origen not in cache:
            cache[origen] = Image.open(ARTE / origen).convert("RGBA")
        fuente = cache[origen]
        # El arte ya viene en proporcion; si el destino no la respeta, se recorta centrado antes
        # de escalar, para no deformarlo.
        destino_prop = w / h
        fuente_prop = fuente.width / fuente.height
        recorte = fuente
        if abs(destino_prop - fuente_prop) > 0.01:
            if fuente_prop > destino_prop:  # sobra ancho
                ancho = int(fuente.height * destino_prop)
                x = (fuente.width - ancho) // 2
                recorte = fuente.crop((x, 0, x + ancho, fuente.height))
            else:  # sobra alto
                alto = int(fuente.width / destino_prop)
                y = (fuente.height - alto) // 2
                recorte = fuente.crop((0, y, fuente.width, y + alto))
        imagen = recorte.resize((w, h), Image.LANCZOS)
        ruta = SALIDA / nombre
        imagen.save(ruta, optimize=True)
        tam = ruta.stat().st_size
        aviso = "  ⚠ pasa de 200 KB" if tam > LIMITE_APPX else ""
        if tam > LIMITE_APPX:
            grandes.append(nombre)
        print(f"  {nombre:<52} {w}x{h}  {tam / 1024:6.1f} KB  <- {origen}{aviso}")

    print(f"\n{len(TILES)} mosaicos en {SALIDA}")
    if grandes:
        print("⚠ por encima del limite de APPX3207: " + ", ".join(grandes))
        print("  con makeappx no suele estorbar; con MSBuild hace falta")
        print("  /p:AppxPackageValidationEnabled=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
