# Los mosaicos del paquete

*(English: [ASSETS.md](ASSETS.md))*

`package/Assets/` está **vacía a propósito**. Los mosaicos del paquete real se hicieron con arte
del propio juego, y eso es de Nintendo: mira [`../NOTICE.es.md`](../NOTICE.es.md). Los tuyos los
pones tú.

`empaquetar_uwp.py` se detiene si falta alguno. Para probar, valen imágenes de color plano del
tamaño correcto.

| Archivo | Tamaño |
|---|---|
| `Square150x150Logo.png` | 300 × 300 |
| `Square150x150Logo.scale-200.png` | 300 × 300 |
| `Square44x44Logo.png` | 88 × 88 |
| `Square44x44Logo.scale-200.png` | 88 × 88 |
| `Square44x44Logo.targetsize-24_altform-unplated.png` | 24 × 24 |
| `Wide310x150Logo.png` | 620 × 300 |
| `Wide310x150Logo.scale-200.png` | 620 × 300 |
| `SplashScreen.png` | 1240 × 600 |
| `SplashScreen.scale-200.png` | 1240 × 600 |
| `StoreLogo.png` | 50 × 50 |
| `StoreLogo.scale-200.png` | 100 × 100 |
| `LockScreenLogo.png` | 48 × 48 |
| `LockScreenLogo.scale-200.png` | 48 × 48 |

Trece archivos. Las variantes `.scale-200` aparecen con el mismo tamaño que su base a propósito:
el manifiesto pide los recursos por nombre lógico y la consola elige la escala que quiere, así que
entregar las dos al tamaño mayor es el arreglo simple que funciona.

`tools/generar_assets.py` arma los trece a partir de unas pocas imágenes de origen, recortando y
rellenando para encajar.

⚠ **Cada mosaico por debajo de 200 KB** si alguna vez empaquetas con MSBuild en vez de `makeappx`:
por encima salta `APPX3207`. `makeappx` no lo comprueba, y por eso esta receta lo usa a él.
