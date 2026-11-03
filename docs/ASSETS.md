# The package tiles

*(Español: [ASSETS.es.md](ASSETS.es.md))*

`package/Assets/` is **empty on purpose**. The tiles of the real package were made from the game's
own artwork, and that is Nintendo's — see [`../NOTICE.md`](../NOTICE.md). You supply your own.

`empaquetar_uwp.py` stops if any of these is missing. Plain colour images of the right size work
fine for testing.

| File | Size |
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

Thirteen files. The `.scale-200` variants are listed at the same size as their base on purpose:
the manifest asks for the assets by logical name and the console picks the scale it wants, so
shipping both at the larger size is the simple, working arrangement.

`tools/generar_assets.py` builds all thirteen from a handful of source images, cropping and
padding to fit.

⚠ **Keep each tile under 200 KB** if you ever package through MSBuild instead of `makeappx`:
`APPX3207` fires above that. `makeappx` does not check, which is why this recipe uses it.
