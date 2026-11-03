# Super Smash Bros. Brawl on Xbox — the UWP port

How to take what **WiiCompiled** produces from your own *Super Smash Bros. Brawl* disc — a native
executable, not an emulator — and run it **on an Xbox Series X in Developer Mode**, as a UWP
package you build and sign yourself.

*(Español: [README.es.md](README.es.md))*

It is not a theory. The port boots, draws, plays its music, reads the controller and runs the
videos on the console at **60 FPS**, with its saves in the package's `LocalState`.

## Which console this was tested on

**An Xbox Series X**, in Developer Mode. That is the only hardware any claim here covers.

**A Series S has never been tried — not once.** It is a different machine: less memory available
to a game and a weaker GPU. This may work on one, it may run slower, or it may not start at all;
nothing here has been measured on it. If you run it on a Series S, what you get is not what this
README reports, and none of the numbers here are a promise about that console.

## What this repository is

**The whole UWP recipe**: the patches, the UWP entry point, and the tools that compile, link,
package and deploy. WiiCompiled builds for the desktop; this is everything that has to change so
the result lives inside an Xbox App Container.

| Piece | What it is |
|---|---|
| `tools/parchar_uwp.py` | **53 patches over 20 files** — 46 in WiiCompiled's runtime (GPL-3.0) and 7 in [Aurora](https://github.com/encounter/aurora) (MIT). This is the port |
| `src/uwp_main.cpp` | The UWP entry point: `SDL_RunApp` → the runtime's `main` |
| `src/compat/unistd.h` | A three-line bridge so zlib compiles against the MSVC ABI |
| `tools/compile_check.py` | The compile pass, inside Visual Studio's **store** environment |
| `tools/enlazar_uwp.py` | The link, with `ld.lld`. The port's worst traps live here |
| `tools/empaquetar_uwp.py` | Package layout, `makeappx` and `signtool` |
| `tools/semilla.ps1` + `src/semilla.cpp` | The **seed package** trick, for when the first install of a package family will not fit |
| `tools/subir_disco.ps1` + `auditar_disco.ps1` | Push the extracted disc to `LocalState`, in batches — **and check afterwards that it all arrived** |
| `tools/semilla_pipelines.py` | Build the shader seed, so the first match does not stutter |
| `tools/xbox-portal.ps1` | A Device Portal client: install, upload, list, launch, screenshot |
| `package/` | The manifest, with `CHANGE-ME` where your identity goes, and the runtime's `Config.toml` |

## What it is not

There is no **disc, no executable, no `.msix`, no tiles, no shader seed and none of the UWP
libraries** (Dawn, SDL3, `nod`, `libuwp`) here — those are either yours or other people's
binaries. `package/Assets/` is empty on purpose and [`docs/ASSETS.md`](docs/ASSETS.md) tells you
what to put in it.

## What you need first

| | |
|---|---|
| **BrawlRecompiled** | Done with **0.5.3**. It compiles your disc to native code; without it there is nothing to port |
| **Your own disc** | *Super Smash Bros. Brawl* `RSBE01`, **revision 1**. Note its build wants a `main_translate.dol` that is **not** the disc's `main.dol`: extracting is not enough, see the project's own instructions |
| **Visual Studio 2022** | With the **C++ UWP component**: its `store` environment is needed (`vcvarsall x64 store`), plus `makeappx`/`signtool` from the Windows SDK |
| **WiiCompiled's llvm-mingw** | clang with the MSVC ABI, which is what compiles and links here |
| **The UWP bundle** | [`worleydl/uwp-dep`](https://github.com/worleydl/uwp-dep), branch **`dawn-dev`**: Dawn, SDL3, `nod`, `dxcompiler` and `libuwp` already built for UWP x64 |
| **Python 3**, **PowerShell 7** and **an Xbox in Developer Mode** | The scripts and the console. Plus a code-signing certificate of your own |

## How it goes

```powershell
# Paths live in environment variables, not in the scripts
$env:BRAWL_WIICOMPILED     = 'D:\brawl\wiicompiled'   # the tree you built for PC
$env:BRAWL_LLVM_MINGW      = 'D:\brawl\toolchain\llvm-mingw'
$env:BRAWL_UWP_DEP         = 'D:\uwp-dep'             # worleydl/uwp-dep, dawn-dev
$env:BRAWL_PLAY            = 'D:\brawl\Play'          # the PC product
$env:BRAWL_CERT_THUMBPRINT = '<your certificate SHA-1>'

# overlay + patch + compile + link + package, in one go
tools\compilar.ps1 -Paso todo -Wiicompiled $env:BRAWL_WIICOMPILED -Build D:\brawl-uwp

# install, push the disc and launch
tools\desplegar.ps1 -Paso todo -Host_ <your Xbox IP> -Build D:\brawl-uwp -Disco D:\brawl\Disc\DATA -Semilla
```

Step by step, including the console side: **[`docs/INSTALL.md`](docs/INSTALL.md)**.

## What it had to solve

The detail is in **[`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md)**.

| | Symptom | Fix |
|---|---|---|
| 1 | The disc indexes as **0 files** and the game dies on its first read | `std::filesystem::relative()` returns empty inside an App Container. `lexically_relative()` instead |
| 2 | `<filesystem>`, `<optional>` and `<algorithm>` come up empty in two units | They leave the compile database with no `-std=`. Fine with libc++, fatal against MSVC's STL |
| 3 | Seven Win32 APIs do not exist in the APP family | `DWM_TIMING_INFO`, `IFileOpenDialog`, `MessageBoxW`, `CreateToolhelp32Snapshot`, `CreateProcessW`, `LoadLibraryExW` and Schannel, each walled off |
| 4 | TLS compiles in neither of the two branches | Schannel is not in the APP family and mbedTLS only enters under `#ifndef _WIN32`. It needed a **third** branch with stubs — Nintendo WFC closed in 2014 |
| 5 | The first install fails with «not enough space» although the console is empty | The first package of a family goes to `D:\DevelopmentFiles`, 5 GB. Install a tiny **seed** first and the real one as an update |
| 6 | The portal answers `OK` and leaves nothing behind | It will not extract a ZIP over ~128 MB. Batches are capped, and bigger files go up unextracted |
| 7 | The game plays, but **with no background music** | The disc upload had been cut short by a full dev partition and nobody noticed. Uploading now **verifies against the source** |
| 8 | Shaders compile mid-match and the frame rate dips | Normal, and it cures itself — but a **seed** of your own makes the first match clean. ⚠ The one WiiCompiled ships is NSMBW's: it shares **1 pipeline out of 393** with Brawl |

## Credits and license

The tools and the recipe are **Recompilaciones**', under the **[GPL-3.0](LICENSE)** — the same
license as WiiCompiled, which is the code the 46 runtime patches modify. The other 7 patch
[Aurora](https://github.com/encounter/aurora), which is MIT, © 2022 Luke Street, and MIT is
compatible with this.

*Super Smash Bros. Brawl* is © Nintendo. WiiCompiled belongs to its author, and
[BrawlRecompiled](https://github.com/josiahg2502-glitch/BrawlRecompiled) to JosiahG — **no line
of the outer project is reproduced here**, only of the GPL-3.0 and MIT trees it carries.

This project is not affiliated with any of them, nor with Microsoft, and distributes nothing that
belongs to them: the detail is in [`NOTICE.md`](NOTICE.md). Rights holders can write to
**jajdpmail@gmail.com**.
