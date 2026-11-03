# Changelog

All notable changes to this recipe. Dates are `YYYY-MM-DD`.

## [1.0.1] — 2026-11-03

### Changed

- **Passages that introduced a fact as "the same as in the other port" now state the fact.** They
  named no repository, so there was nothing for the reader to go and look up, and the fact itself
  went unsaid. The disk-space warning told you to run a script that is **not in this repository**,
  over another port's folder. It now says how to free the space from the Device Portal.

  Still said, because the reader can act on it: everything that is **not** ours — the upstream
  project, the third-party forks, the files taken under their own license — and the sentences that
  place this port among others without naming any, which stand on their own.

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
