# Changelog

All notable changes to this recipe. Dates are `YYYY-MM-DD`.

## [1.0.0] — 2026-11-03

First public release. The port boots, draws, plays sound and reads the controller on an Xbox
Series X in Developer Mode at 60 FPS.

### The recipe

- **53 patches over 20 files** (`tools/parchar_uwp.py`): 46 in WiiCompiled's runtime and 7 in
  Aurora. Built against **BrawlRecompiled 0.5.3**.
- UWP entry point (`src/uwp_main.cpp`) and a zlib bridge for the MSVC ABI
  (`src/compat/unistd.h`).
- Compile, link, package and sign: `compile_check.py`, `enlazar_uwp.py`, `empaquetar_uwp.py`,
  driven by `compilar.ps1`.
- Deploy to the console: `desplegar.ps1`, `xbox-portal.ps1`, `subir_disco.ps1`,
  `auditar_disco.ps1`, `xbox-vaciar-carpeta.ps1`.
- The **seed package** trick for the first install of a package family (`semilla.ps1`,
  `src/semilla.cpp`).
- The **shader seed** builder (`semilla_pipelines.py`).

### What was solved along the way

- `std::filesystem::relative()` returns empty inside an App Container — the disc indexed as
  0 files. Replaced with `lexically_relative()`.
- Two units reaching the compiler with no `-std=`, fatal against MSVC's STL.
- Seven Win32 APIs absent from the APP family, plus a third TLS branch with stubs.
- The ~128 MB ceiling on ZIPs the portal will extract, and the fixed ~30 GB dev partition.
- **A disc upload that stopped part-way and said nothing**: 223 of 314 music files were missing
  and the game played on in silence. Uploads now verify against the source.
- The shader-compilation stutter of a first match, and why WiiCompiled's own seed does not help
  this game (1 shared pipeline out of 393).
