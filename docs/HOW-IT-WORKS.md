# How the port works, and what it had to solve

*(Español: [HOW-IT-WORKS.es.md](HOW-IT-WORKS.es.md))*

WiiCompiled recompiles the PowerPC code of a Wii disc into native C++. Its product is a desktop
Windows program. An Xbox in Developer Mode will not run that: it runs **UWP packages inside an App
Container**, a sandbox where a good part of Win32 simply is not there.

So the port is not a rewrite. It is **53 patches over 20 files**, a UWP entry point, and a build
that uses clang against the MSVC ABI instead of the normal desktop toolchain.

## The shape of it

| | |
|---|---|
| Compiler | clang from WiiCompiled's llvm-mingw, `--target=x86_64-pc-windows-msvc`, with `-DWINAPI_FAMILY=WINAPI_FAMILY_APP`, inside `vcvarsall x64 store` |
| Linker | `ld.lld -flavor link /appcontainer /subsystem:windows,10.0` |
| Graphics | Aurora over Dawn (WebGPU), from `worleydl/uwp-dep`, branch `dawn-dev` |
| Entry point | `src/uwp_main.cpp`: `SDL_RunApp` → the runtime's `main` |
| Result | ~1.250 units, one `.exe` of ~176 MB with the game inside it |

The feature macro is **`MKW_UWP`**, and it stays that way. The whole WiiCompiled runtime uses the
`MKW_` prefix (`MKW_PPC_*`, `MKW_FLAT_GUEST_BASE`, `MKW_CRYPTOPP_ALLOW_CLANG_MSVC_ABI`), so it is
the runtime's prefix, not the game's. Renaming it would just make the patches diverge from
upstream for nothing.

## 1. The disc indexes as zero files

The worst one, because it looks like a packaging problem. The runtime walks the disc directory and
builds its index with:

```cpp
const fs::path relative = fs::relative(entry.path(), root, entryEc);
```

Inside an App Container, **`std::filesystem::relative()` returns an empty path**. No exception, no
error code worth reading: the index comes out with zero entries, the log says
`[dvd] disc index: 0 disc file(s)`, and the game dies on its first read. The fix is to compute it
lexically, which needs no filesystem access at all:

```cpp
#if defined(MKW_UWP)
        const fs::path relative = entry.path().lexically_relative(root);
        if (relative.empty()) { return; }
#else
        const fs::path relative = fs::relative(entry.path(), root, entryEc);
        if (entryEc) { return; }
#endif
```

## 2. Two units that compile without a standard

`host_platform.cpp` and `input_expr.cpp` come out of the compile database with no `-std=` flag,
because they belong to targets of their own. Against libc++ the default was good enough; against
MSVC's STL it means `<filesystem>`, `<optional>` and `<algorithm>` come up **empty** and you get a
wall of errors that look like missing headers. `compile_check.py` adds `-std=gnu++20` to any unit
that arrives without one.

## 3. Win32 that does not exist in the APP family

Seven places, each walled off behind `#if !defined(MKW_UWP)`:

| Where | What |
|---|---|
| `hle/vi.cpp` | `DWM_TIMING_INFO` |
| `game_folder.cpp` | `IFileOpenDialog` and `shobjidl.h` — it already had an `#else` returning true |
| `product/engine_loader.cpp` | `MessageBoxW` → `OutputDebugStringW`, and `LoadLibraryExW` → `LoadPackagedLibrary` |
| `hle/sampling_profiler.cpp` | `CreateToolhelp32Snapshot` |
| `netplay/netplay_lobby.cpp` | `CreateProcessW` |
| `product/engine_loader.cpp` | `cpuid.h` is a GCC header and clashes with `intrin.h` under the MSVC ABI: `__cpuid_count` rewritten with `__cpuidex` |
| `runtime_config.h` | `SHGetKnownFolderPath` — data goes to the package's `LocalState` |

## 4. TLS needed a third branch

`hle/net/network_ssl.cpp` has two paths and **neither compiles here**. Schannel (`CredHandle`,
`SCHANNEL_CRED`) is not in the APP family, and the `#include <mbedtls/*>` path only enters under
`#ifndef _WIN32`. So a third branch was added with stubs returning `SSL_ERR_FAILED`
(`ClearSslSession`, `SslHandshakeImpl`, `SslWrite`, `SslRead`). Nothing is lost: Nintendo WFC shut
down in 2014.

## 5. zlib against the MSVC ABI

`third_party/cryptopp/zdeflate.cpp` pulls in `<unistd.h>`, which MSVC does not have.
`src/compat/unistd.h` is a three-line bridge to `<io.h>` and `<process.h>`, added to the include
path only for those units.

## 6. The first install does not fit

The first package of a **family** is placed in `D:\DevelopmentFiles`, about 5 GB and usually full,
and the portal answers «There is not enough space on the disk» even when the console looks empty.

The way around it is the **seed**: a minimal package with the same identity at version 0.1.0.0
(`src/semilla.cpp` is a `main` that does nothing). Install that first; the real package then goes
in **as an update**, which is placed elsewhere. `tools/semilla.ps1` builds and signs it.

## 7. The portal lies about large ZIPs

`subir_disco.ps1` sends the disc as ZIPs that the console extracts. Measured on 2026-11-02 with
4,5 GB free: batches of 117 MB and 122 MB go in; one of 150 MB answers `InternalServerError`. The
cut-off is around **128 MB**, so batches are capped at 100 MB and any single file above that is
uploaded **without** extraction (in Brawl, the four big `.thp` videos).

And a separate limit that is easy to confuse with it: the dev storage is a **fixed ~30 GB
partition** for every dev package on the console, nothing to do with the 800 GB of games.

## 8. The silent failure: a game with no music

This one is worth its own section, because it did not look like a failure at all.

With the dev partition full, the disc upload stopped part-way. The script checked each batch's
response, so it reported no error for what it sent — but **it never reported what it had not
sent**. The result: 91 of the 314 `.brstm` files made it, cut off cleanly in alphabetical order.
The package installed, the game booted, ran at 60 FPS and played a full match. It just had no
background music, and nothing anywhere said so: the game asks for a stream file, it is not there,
and it carries on in silence.

The lesson is in `auditar_disco.ps1`, which `subir_disco.ps1` now calls when it finishes: **an
upload is not done when the portal says OK, it is done when the destination has been read back and
matches the source**, name and size, file by file.

Two things about the portal that came out of fixing it:

- **It does not overwrite.** Re-uploading an existing file creates `name_0.ext`, `name_1.ext`…
  So re-uploading everything "just in case" duplicates and eats the very space you are short of.
- The size field in its JSON is **`FileSize`**, not `Size`. Reading the wrong one made
  `xbox-vaciar-carpeta.ps1` report «0.0 MB» for every folder, which almost hid the 480 MB of logs
  that were the easiest space to free.

## 9. The shaders, and the seed

The Wii has no shaders: it has the **TEV**, configured through registers. Aurora translates each
combination the game uses into WGSL, and Dawn compiles it — the first time that material appears
on screen. Hence the stutter in a first match, the same phenomenon as Dolphin's shader compilation
stutter.

It does not freeze, because `skip_unready_pipelines` is on by default (and in the F10 menu as
«Skip draws while shaders compile»): while a pipeline is not ready that draw is **skipped** rather
than blocking. That is why it reads as a frame-rate dip and not as a hitch.

It cures itself because there are two caches, and they are different things:

| File | What | Portable |
|---|---|---|
| `Cache/pipeline_cache.db` | GX pipeline **descriptions**, no code and no game data | **yes**, between machines, and between PC and Xbox |
| `Cache/dawn_cache.db` | the blob Dawn already compiled | no, that GPU only |

At startup Aurora rebuilds **everything** in `pipeline_cache.db` — no `LIMIT`, ordered by
`first_frame_used` — so each session starts knowing more. Measured here: a boot went from
prewarming 12 pipelines to **434 in 21,7 s** after seeding it, and to 1.298 once the game had been
played more.

`tools/semilla_pipelines.py` merges caches from sessions already played into a seed that ships
inside the package. Three traps:

- **The `-wal` counts.** Copy the `.db` **with its `-wal` next to it** or you lose exactly the most
  recent sessions. And when installing one on the console: stop the app, delete the old `-wal` and
  `-shm`, *then* upload — otherwise SQLite replays the old journal over the new file.
- **`config_version`.** Aurora loads with `WHERE type = ? AND config_version = ?`; a seed built
  with another runtime version is **ignored in silence**.
- **It must be this game's.** The one WiiCompiled ships is NSMBW's: 1 shared pipeline out of 393.
