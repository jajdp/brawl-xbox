# Building and installing it, step by step

*(Español: [INSTALL.es.md](INSTALL.es.md))*

Everything here was done on **an Xbox Series X** in Developer Mode. A Series S has never been
tried; see the warning in the [README](../README.md).

## 0. Before anything: the PC build has to work

This repository ports **the result** of BrawlRecompiled, so first get that building and running on
your PC, following *its* instructions. You need its `Play\` product working before porting
anything. Two things its README leaves out and cost time:

- `extract_wbfs.py` **only accepts `.wbfs`**. An `.iso` has to be converted first.
- **The translator is not shipped built**: `dotnet build wiicompiled/translator/Translator.sln -c Release`.

The disc is *Super Smash Bros. Brawl* `RSBE01` **revision 1**, and the manifest wants a
`main_translate.dol` that is **not** the `main.dol` on the disc — it is that one plus the resident
modules, which `tools/build_modules.py` assembles. Extracting the disc is not enough.

## 1. The Device Portal credentials

The deploy scripts talk to the console over the Device Portal, with Basic auth. They read the
user and password from a file **outside this repository**:

```
%LOCALAPPDATA%\xbox-devportal\credenciales.txt
```

One single line, `user:password`, exactly as the console shows them in **Settings → Developer
settings** when you enable remote access. Create it by hand:

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\xbox-devportal" | Out-Null
Set-Content "$env:LOCALAPPDATA\xbox-devportal\credenciales.txt" 'youruser:yourpassword' -NoNewline
```

⚠ **Never put those credentials in a script, a commit or an issue.** They are the keys to your
console over your network. `.gitignore` blocks `credenciales.txt`, but the real protection is not
writing them anywhere else.

## 2. Environment

```powershell
$env:BRAWL_WIICOMPILED     = 'D:\brawl\wiicompiled'
$env:BRAWL_LLVM_MINGW      = 'D:\brawl\toolchain\llvm-mingw'
$env:BRAWL_UWP_DEP         = 'D:\uwp-dep'            # worleydl/uwp-dep, branch dawn-dev
$env:BRAWL_PLAY            = 'D:\brawl\Play'
$env:BRAWL_CERT_THUMBPRINT = '<SHA-1 of your code-signing certificate>'
```

The certificate is yours. Its **CN must match** the `Publisher` in `package/Package.appxmanifest`:
the package family hash is derived from that `Publisher`, so if they differ the package will not
install. Either change the manifest's `Publisher` to your CN, or make a certificate with the CN
that is in there.

```powershell
New-SelfSignedCertificate -Type Custom -Subject 'CN=YourName' -KeyUsage DigitalSignature `
  -CertStoreLocation 'Cert:\CurrentUser\My' -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3')
```

The console must trust it: export the **public** part (`.cer`, never the `.pfx`) and install it on
the Xbox with `tools\xbox-portal.ps1 certificado`.

## 3. Build

```powershell
tools\compilar.ps1 -Paso todo -Wiicompiled $env:BRAWL_WIICOMPILED -Build D:\brawl-uwp
```

The steps, if you want them one at a time: `overlay`, `parchar`, `compdb`, `compilar`, `enlazar`,
`semilla`, `empaquetar`.

⚠ **`parchar` is not idempotent. Only ever run it on a clean overlay.** The recipe has pairs of
cascading patches: one inserts a provisional block inside a function and the next replaces it with
the clean call. Applied twice, the provisional one goes back in, the block ends up duplicated and
you get `expected unqualified-id` — a linkage specification cannot live inside a function. The
`overlay` step rebuilds the tree with `robocopy /E /IS /IT` precisely so that `parchar` gets a
clean one.

The compile is ~1.250 units. The link produces a single `SuperSmashBrosBrawl.exe` of about 176 MB:
unlike the PC build, the game is inside the executable, not in an `engine_usa.dll`.

## 4. Install on the console

```powershell
tools\desplegar.ps1 -Paso instalar -Host_ <IP> -Build D:\brawl-uwp -Semilla
```

**`-Semilla` matters on the first install of this package family.** The first package of a family
goes to `D:\DevelopmentFiles`, which is about 5 GB and tends to be full, and you get
«There is not enough space on the disk» even on an empty console. The seed is a minimal package
with the same identity at version 0.1.0.0: it registers the family, and the real package then
installs **as an update**, which lands elsewhere. On later installs, drop `-Semilla`.

## 5. Push the disc

The game reads its data from `LocalState\GameAssets\DATA`, not from inside the package: 6.7 GB
that survive reinstalling.

```powershell
tools\desplegar.ps1 -Paso disco -Host_ <IP> -Build D:\brawl-uwp -Disco D:\brawl\Disc\DATA
```

Two hard limits of the console, and they are not the same one:

- **The dev storage is a fixed ~30 GB partition** shared by every dev package. Nothing to do with
  the 800 GB of games. When it fills up, the portal answers «There is not enough space on the
  disk» to *everything*, even a 4 KB file. To make room without losing saves:
  `tools\xbox-vaciar-carpeta.ps1`. **Look at the port's own `Logs` folder first** — ours held
  480 MB of per-session dumps.
- **The portal will not extract a ZIP over ~128 MB**, and answers `OK` anyway. Batches are capped
  at 100 MB and anything bigger goes up unextracted.

⚠ **The upload verifies itself when it finishes**, with `auditar_disco.ps1`. Do not skip it. We
learned this the bad way: an upload cut short by a full partition left 223 of the 314 `.brstm`
music files behind, and the game installed, booted and played a whole match **with no background
music** and no error anywhere. If it reports missing files, free space and re-run with
`-Lista <the report it wrote>`.

## 6. Config and launch

```powershell
tools\desplegar.ps1 -Paso config -Host_ <IP> -Build D:\brawl-uwp
tools\desplegar.ps1 -Paso lanzar -Host_ <IP> -Build D:\brawl-uwp
```

`Config.toml` goes to `LocalState\WiiCompiled\`. `dvd_root = "../GameAssets/DATA"` is what points
the runtime at the disc.

Launching through the portal fails with `-2147023880` now and then and works on the second try;
the script retries. The screenshot comes back empty while the screen is mid-transition — it
retries too.

## 7. First match: the shaders

The first time each character, stage and effect appears, Aurora translates its TEV setup into a
shader and Dawn compiles it. You will see the frame rate dip. **It is normal and it cures itself**:
every pipeline is saved in `LocalState\WiiCompiled\Cache\pipeline_cache.db` and rebuilt in bulk at
the next launch.

To skip that first rough match, build a seed from sessions you have already played:

```powershell
python tools\semilla_pipelines.py
```

It merges the console's cache with your PC's — they are portable between machines — and writes
`package/initial_pipeline_cache.db`, which `empaquetar_uwp.py` then puts inside the package.

⚠ **Do not use the `initial_pipeline_cache.db` that WiiCompiled ships.** The CMake copies it for
all four of its projects, but its contents are New Super Mario Bros. Wii's: measured here, it
shares **1 pipeline out of 393** with Brawl. It would compile 1.155 shaders this game never asks
for, making startup longer without removing a single stutter.
