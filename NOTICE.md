# Notice

*(Español: [NOTICE.es.md](NOTICE.es.md))*

## Not affiliated

This is an unofficial, noncommercial fan project. It is **not affiliated with, endorsed by or
connected to Nintendo or Microsoft**, nor to the author of WiiCompiled, nor to JosiahG
(BrawlRecompiled), nor to the author of [Aurora](https://github.com/encounter/aurora).
*Super Smash Bros. Brawl*, *Xbox* and all related names and marks are the property of their
respective owners, and are used here only to say what this works with.

Nothing here is for sale, and nothing here is monetized.

## What this repository does not distribute

No disc image. No game data — no `.pac`, no `.brres`, no `.brstm`, no `.thp`, no `.brsar`. No
built executable. No `.msix`. No save data. No package tiles (`package/Assets/` is empty, and
[`docs/ASSETS.md`](docs/ASSETS.md) asks you to supply your own).

**No shader seed either.** `initial_pipeline_cache.db` is derived from running your own disc;
`tools/semilla_pipelines.py` builds yours from your own play sessions.

**And none of the UWP libraries**: Dawn, SDL3, `nod`, `libuwp`, `dxcompiler`, libpng and zlib are
other people's binaries. The guide says where they come from.

**There are no screenshots here.** A screenshot of this running would be mostly Nintendo's artwork.

## What it does contain of other people's work, and under what permission

This was measured file by file before publishing. **53 patches over 20 files:**

| Tree | Patches | Its license | Why that is allowed |
|---|---|---|---|
| WiiCompiled's `runtime/` | **46** | **GPL-3.0** (`wiicompiled/LICENSE`, the FSF text) | The GPL grants the right to modify and redistribute, provided the derivative carries the same license. This repository is **GPL-3.0** |
| [Aurora](https://github.com/encounter/aurora) | **7** | **MIT**, © 2022 Luke Street | MIT permits modified versions, and is compatible with the GPL-3.0 this repository uses. Aurora's own copyright notice travels with it |
| BrawlRecompiled, the outer project | **0** | none declared | With no license granting it, **not one line** is reproduced: not as a diff, not as patch anchors, not as quoted lines |

That last row is the point. [BrawlRecompiled](https://github.com/josiahg2502-glitch/BrawlRecompiled)
declares no license of its own; what carries one is the code **inside** it — `wiicompiled/LICENSE`
is the GPL-3.0, and `aurora-main/LICENSE` is MIT. The patches here touch only those two trees, and
that is what makes them publishable. Nothing of the outer project's own code is here.

The tooling in `tools/` and the entry point in `src/` are first-party.

## Takedown and contact

If you hold rights in this material and want something here removed or changed, write to
**jajdpmail@gmail.com**, saying what you object to and in what capacity you are writing.

Requests from rights holders are honoured: the disputed part is removed, or the repository is
taken down, without argument, and you will get a reply confirming it. No notice or legal process
beyond that email is needed to reach the person who maintains this.
