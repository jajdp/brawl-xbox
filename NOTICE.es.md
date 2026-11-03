# Aviso

*(English: [NOTICE.md](NOTICE.md))*

## Sin afiliación

Es un proyecto de aficionado, no oficial y sin ánimo de lucro. **No está afiliado, ni respaldado,
ni conectado con Nintendo ni con Microsoft**, ni con el autor de WiiCompiled, ni con JosiahG
(BrawlRecompiled), ni con el autor de [Aurora](https://github.com/encounter/aurora).
*Super Smash Bros. Brawl*, *Xbox* y todos los nombres y marcas relacionados son propiedad de sus
titulares, y aquí se usan solo para decir con qué funciona esto.

Nada de esto está a la venta ni se monetiza.

## Qué NO distribuye este repositorio

Ninguna imagen de disco. Ningún dato del juego: ni `.pac`, ni `.brres`, ni `.brstm`, ni `.thp`, ni
`.brsar`. Ningún ejecutable compilado. Ningún `.msix`. Ninguna partida. Ningún mosaico del paquete
(`package/Assets/` está vacía y [`docs/ASSETS.es.md`](docs/ASSETS.es.md) pide que pongas los tuyos).

**Tampoco la semilla de shaders.** El `initial_pipeline_cache.db` sale de ejecutar tu propio disco;
`tools/semilla_pipelines.py` arma el tuyo a partir de tus propias partidas.

**Ni ninguna de las bibliotecas UWP**: Dawn, SDL3, `nod`, `libuwp`, `dxcompiler`, libpng y zlib son
binarios de otros. La guía dice de dónde salen.

**Aquí no hay capturas de pantalla.** Una captura de esto funcionando sería, en su mayor parte,
arte de Nintendo.

## Qué contiene de obra ajena, y con qué permiso

Esto se midió archivo por archivo antes de publicar. **53 parches sobre 20 archivos:**

| Árbol | Parches | Su licencia | Por qué se puede |
|---|---|---|---|
| El `runtime/` de WiiCompiled | **46** | **GPL-3.0** (`wiicompiled/LICENSE`, el texto de la FSF) | La GPL concede el derecho a modificar y redistribuir, siempre que la obra derivada lleve la misma licencia. Este repositorio es **GPL-3.0** |
| [Aurora](https://github.com/encounter/aurora) | **7** | **MIT**, © 2022 Luke Street | MIT permite versiones modificadas y es compatible con la GPL-3.0 que usa este repositorio. Su aviso de copyright viaja con el código |
| BrawlRecompiled, el proyecto contenedor | **0** | ninguna declarada | Sin una licencia que lo permita, **no se reproduce ni una línea**: ni como diff, ni como anclas de parche, ni como líneas citadas |

Esa última fila es lo importante. [BrawlRecompiled](https://github.com/josiahg2502-glitch/BrawlRecompiled)
no declara licencia propia; lo que sí la tiene es el código **que lleva dentro**:
`wiicompiled/LICENSE` es la GPL-3.0 y `aurora-main/LICENSE` es MIT. Los parches de aquí tocan solo
esos dos árboles, y eso es lo que los hace publicables. Del código propio del proyecto contenedor
no hay nada.

Las herramientas de `tools/` y la entrada de `src/` son de cosecha propia.

## Retirada y contacto

Si tienes derechos sobre este material y quieres que se quite o se cambie algo, escribe a
**jajdpmail@gmail.com**, diciendo a qué te opones y en calidad de qué escribes.

Las peticiones de los titulares de derechos se atienden: se retira la parte en disputa, o el
repositorio entero, sin discutir, y recibirás una respuesta confirmándolo. No hace falta ningún
aviso ni procedimiento legal más allá de ese correo para llegar a quien mantiene esto.
