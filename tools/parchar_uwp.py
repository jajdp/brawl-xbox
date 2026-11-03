"""Aplica los parches UWP sobre la copia de trabajo xbox\\port (runtime y aurora-main de
Wiicompiled del arbol de Brawl). Cada parche exige que el texto viejo aparezca exactamente n veces.
Todo el delta queda bajo MKW_UWP (runtime) o AURORA_WINDOWS_STORE (aurora), así que el
mismo árbol sigue compilando para PC. Idempotente: si el texto nuevo ya está, no toca."""
import sys
from pathlib import Path

if len(sys.argv) < 2:
    raise SystemExit("uso: parchar_uwp.py <ruta del overlay a parchear>\n"
                     "  el overlay es la copia de runtime/, aurora-main/ y projects/\n"
                     "  sobre la que se trabaja; NUNCA el arbol original.")
PORT = Path(sys.argv[1])

P = []  # (archivo relativo, viejo, nuevo, veces)

# ---------------- runtime ----------------
# Brawl: ApplicationDataDirectory() ya no empieza en LOCALAPPDATA, sino en Documents, asi que la
# rama de Windows se corta antes del #ifdef _WIN32 y no en medio.
P.append(("runtime/include/runtime_config.h",
r'''    if (const auto& portableRoot = PortableRootDirectory()) {
        return *portableRoot / kPortableUserDataDirectoryName;
    }
#ifdef _WIN32
    static const std::optional<std::filesystem::path> documents = []() -> std::optional<std::filesystem::path> {''',
r'''    if (const auto& portableRoot = PortableRootDirectory()) {
        return *portableRoot / kPortableUserDataDirectoryName;
    }
#if defined(MKW_UWP)
    // UWP: no hay SHGetKnownFolderPath ni Documents; los datos del usuario van a LocalState del
    // paquete (RuntimePlatform::ApplicationDataDirectory, host_platform.cpp).
    return RuntimePlatform::ApplicationDataDirectory(kApplicationDirectoryName);
#elif defined(_WIN32)
    static const std::optional<std::filesystem::path> documents = []() -> std::optional<std::filesystem::path> {''', 1))

# Y el tercer SHGetKnownFolderPath, el de AdoptEarlierUserData, que vive dentro del #ifdef _WIN32
# y por tanto si entraria en la compilacion de UWP.
P.append(("runtime/include/runtime_config.h",
r'''    PWSTR localPath = nullptr;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &localPath)) && localPath) {
        candidates.push_back(std::filesystem::path(localPath) / kApplicationDirectoryName);
        CoTaskMemFree(localPath);
    }''',
r'''#if !defined(MKW_UWP)
    // UWP: SHGetKnownFolderPath no esta en la API del AppContainer, y en la consola no hay datos
    // de una version anterior que adoptar: todo vive en el LocalState del paquete.
    PWSTR localPath = nullptr;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &localPath)) && localPath) {
        candidates.push_back(std::filesystem::path(localPath) / kApplicationDirectoryName);
        CoTaskMemFree(localPath);
    }
#endif''', 1))

P.append(("runtime/src/platform/host_platform.cpp",
r'''#include <windows.h>
#include <shlobj.h>''',
r'''#include <windows.h>
#include <shlobj.h>
#if defined(MKW_UWP)
#include <SDL3/SDL_filesystem.h>
#include <SDL3/SDL_stdinc.h>
#endif''', 1))

P.append(("runtime/src/platform/host_platform.cpp",
r'''std::filesystem::path ApplicationDataDirectory(std::string_view applicationName) {
#if defined(_WIN32)
    PWSTR rawPath = nullptr;''',
r'''std::filesystem::path ApplicationDataDirectory(std::string_view applicationName) {
#if defined(MKW_UWP)
    // AppContainer: la única carpeta de datos escribible y visible por el Device Portal es
    // LocalState. SDL3-uwp devuelve <LocalState>\<applicationName>\ (y la crea).
    if (char* pref = SDL_GetPrefPath(nullptr, std::string(applicationName).c_str())) {
        std::filesystem::path directory(pref);
        SDL_free(pref);
        return directory.lexically_normal();
    }
#elif defined(_WIN32)
    PWSTR rawPath = nullptr;''', 1))

P.append(("runtime/src/host_cpu_baseline.cpp",
r'''#if defined(_WIN32)
    ::MessageBoxA(nullptr, message.data, "WiiCompiled - Unsupported Processor",''',
r'''#if defined(_WIN32) && !defined(MKW_UWP)
    ::MessageBoxA(nullptr, message.data, "WiiCompiled - Unsupported Processor",''', 1))

P.append(("runtime/src/main.cpp",
r'''    ::SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);''',
r'''#if !defined(MKW_UWP)
    ::SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
#endif''', 1))

P.append(("runtime/src/main.cpp",
r'''        const MMRESULT result = ::timeBeginPeriod(1);
        if (result == TIMERR_NOERROR) {
            armed_ = true;
        } else {
            RT_LOG(RT_TAG_RUNTIME) << "timeBeginPeriod(1) failed: " << result << std::endl;
        }''',
r'''#if !defined(MKW_UWP)
        const MMRESULT result = ::timeBeginPeriod(1);
        if (result == TIMERR_NOERROR) {
            armed_ = true;
        } else {
            RT_LOG(RT_TAG_RUNTIME) << "timeBeginPeriod(1) failed: " << result << std::endl;
        }
#endif''', 1))

P.append(("runtime/src/main.cpp",
r'''        if (armed_) {
            ::timeEndPeriod(1);
        }''',
r'''#if !defined(MKW_UWP)
        if (armed_) {
            ::timeEndPeriod(1);
        }
#endif''', 1))

P.append(("runtime/src/main.cpp",
r'''#if defined(_WIN32)
    int pipeFds[2]{-1, -1};
    if (_pipe(pipeFds, 8192, _O_BINARY) != 0) {
        return false;
    }''',
r'''#if defined(MKW_UWP)
    // UWP: la CRT no expone _pipe(). stdout/stderr ya apuntan a un archivo de LocalState
    // (AttachParentConsoleForDiagnostics), así que la transcripción por tubería sobra.
    int pipeFds[2]{-1, -1};
    (void)targetFd;
    return false;
#elif defined(_WIN32)
    int pipeFds[2]{-1, -1};
    if (_pipe(pipeFds, 8192, _O_BINARY) != 0) {
        return false;
    }''', 1))

P.append(("runtime/src/main.cpp",
r'''    const bool attached =
        ::GetConsoleWindow() != nullptr || ::AttachConsole(ATTACH_PARENT_PROCESS) != 0;
    const char* const sink = attached ? "CONOUT$" : "NUL";''',
r'''#if defined(MKW_UWP)
#define MKW_SINK_MODE "a"
    // UWP: no hay consola. stdout y stderr van a LocalState\WiiCompiled\Logs\uwp-console.txt,
    // que se puede leer por el Device Portal de la consola.
    std::error_code ec;
    const std::filesystem::path logDir = RuntimeConfigFile::ApplicationDataDirectory() / "Logs";
    std::filesystem::create_directories(logDir, ec);
    std::filesystem::remove(logDir / "uwp-console.txt", ec);
    const std::string sinkPath = (logDir / "uwp-console.txt").string();
    const char* const sink = sinkPath.c_str();
#else
#define MKW_SINK_MODE "w"
    const bool attached =
        ::GetConsoleWindow() != nullptr || ::AttachConsole(ATTACH_PARENT_PROCESS) != 0;
    const char* const sink = attached ? "CONOUT$" : "NUL";
#endif''', 1))

P.append(("runtime/src/main.cpp",
r'''        (void)std::freopen(sink, "w", stdout);''',
r'''        (void)std::freopen(sink, MKW_SINK_MODE, stdout);''', 1))

P.append(("runtime/src/main.cpp",
r'''        (void)std::freopen(sink, "w", stderr);''',
r'''        (void)std::freopen(sink, MKW_SINK_MODE, stderr);''', 1))

P.append(("runtime/src/main.cpp",
r'''std::string FormatHostStackTrace(unsigned framesToSkip) {
#if defined(_WIN32)
    static std::atomic_bool s_symbolsReady{false};''',
r'''std::string FormatHostStackTrace(unsigned framesToSkip) {
#if defined(MKW_UWP)
    (void)framesToSkip;
    return "[runtime] host stack trace unavailable on UWP (no DbgHelp)\n";
#elif defined(_WIN32)
    static std::atomic_bool s_symbolsReady{false};''', 1))

P.append(("runtime/src/main.cpp",
r'''#if defined(_WIN32)
        ::MessageBoxA(nullptr, message.c_str(), "WiiCompiled - Fatal Error",''',
r'''#if defined(_WIN32) && !defined(MKW_UWP)
        ::MessageBoxA(nullptr, message.c_str(), "WiiCompiled - Fatal Error",''', 1))

P.append(("runtime/src/main.cpp",
r'''int main(int argc, char** argv) {
    return RuntimeMain(argc, argv);
}''',
r'''#if !defined(MKW_UWP)
int main(int argc, char** argv) {
    return RuntimeMain(argc, argv);
}
#endif''', 1))

P.append(("runtime/src/memory.cpp",
r'''#if defined(_WIN32)
    void* frames[32]{};
    const USHORT captured = CaptureStackBackTrace(0, static_cast<DWORD>(std::size(frames)), frames, nullptr);''',
r'''#if defined(_WIN32) && !defined(MKW_UWP)
    void* frames[32]{};
    const USHORT captured = CaptureStackBackTrace(0, static_cast<DWORD>(std::size(frames)), frames, nullptr);''', 1))

P.append(("runtime/src/host_context.cpp",
r'''    void* context = ConvertThreadToFiber(nullptr);''',
r'''    void* context = ConvertThreadToFiberEx(nullptr, 0);  // la variante Ex existe en la familia UWP''', 1))

P.append(("runtime/src/host_context.cpp",
r'''    return CreateFiber(stackSize, entry, argument);''',
r'''    return CreateFiberEx(0, stackSize, 0, entry, argument);  // idem''', 1))

P.append(("runtime/src/guest_flat_memory.cpp",
r'''#endif
#include <windows.h>''',
r'''#endif
#include <windows.h>
#if defined(MKW_UWP)
// El SDK no declara los manejadores vectoriales para WINAPI_FAMILY_APP, pero kernel32 los
// exporta y AppContainer los permite: se declaran a mano.
extern "C" {
__declspec(dllimport) PVOID WINAPI AddVectoredExceptionHandler(ULONG First, PVECTORED_EXCEPTION_HANDLER Handler);
__declspec(dllimport) ULONG WINAPI RemoveVectoredExceptionHandler(PVOID Handle);
}
#endif''', 1))

P.append(("runtime/src/discord_presence.cpp",
r'''            handle_ = ::CreateFileA(name.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);''',
r'''#if defined(MKW_UWP)
            handle_ = INVALID_HANDLE_VALUE;  // sin tuberías con nombre dentro de AppContainer
            (void)name;
#else
            handle_ = ::CreateFileA(name.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
#endif''', 1))

P.append(("runtime/src/hle/net/network_ssl.cpp",
r'''#ifdef _WIN32''',
r'''#if defined(_WIN32) && !defined(MKW_UWP)  /* UWP: sin Schannel, usa los stubs de abajo */''', 3))

# cryptopp: con clang en ABI MSVC el STL define _STDEXT_BEGIN pero cryptopp no define
# CRYPTOPP_MSC_VERSION, y cae en stdext::unchecked_mismatch, que el STL de VS 2022 ya no trae.
P.append(("runtime/third_party/cryptopp/zdeflate.cpp",
"#if defined(_STDEXT_BEGIN) && !(defined(CRYPTOPP_MSC_VERSION)",
"#if defined(_STDEXT_BEGIN) && !defined(__clang__) && !(defined(CRYPTOPP_MSC_VERSION)", 1))

P.append(("runtime/third_party/cryptopp/zdeflate.cpp",
"#if CRYPTOPP_MSC_VERSION >= 1600\n\t\t\t\t(stdext::make_unchecked_array_iterator(scan)+3",
"#if CRYPTOPP_MSC_VERSION >= 1600 && !defined(__clang__)\n\t\t\t\t(stdext::make_unchecked_array_iterator(scan)+3", 1))

# main.cpp también instala un manejador vectorial (el reporte de fallos): misma declaración
P.append(("runtime/src/main.cpp",
r'''#include <windows.h>
#include <mmsystem.h>
#include <dbghelp.h>''',
r'''#include <windows.h>
#include <mmsystem.h>
#include <dbghelp.h>
#if defined(MKW_UWP)
extern "C" {
__declspec(dllimport) PVOID WINAPI AddVectoredExceptionHandler(ULONG First, PVECTORED_EXCEPTION_HANDLER Handler);
__declspec(dllimport) ULONG WINAPI RemoveVectoredExceptionHandler(PVOID Handle);
}
#endif''', 1))

# Trazas de arranque en UWP (van a \AC\Temp\mkw-uwp-traza.txt, ver uwp_main.cpp)
P.append(("runtime/src/host_cpu_baseline.cpp",
r'''    WriteStdErrEarly("[runtime] ");
    WriteStdErrEarly(message.data);
    WriteStdErrEarly("\n");''',
r'''    WriteStdErrEarly("[runtime] ");
    WriteStdErrEarly(message.data);
    WriteStdErrEarly("\n");
#if defined(MKW_UWP)
    { extern "C" void MkwUwpTrace(const char*); MkwUwpTrace(message.data); }
#endif''', 1))

P.append(("runtime/src/main.cpp",
r'''        RT_LOGF(RT_TAG_RUNTIME, "fatal dialog: %s\n", message.c_str());''',
r'''        RT_LOGF(RT_TAG_RUNTIME, "fatal dialog: %s\n", message.c_str());
#if defined(MKW_UWP)
        { extern "C" void MkwUwpTrace(const char*); MkwUwpTrace(message.c_str()); }
#endif''', 1))

# Corrección: una linkage-specification (extern "C") no puede ir dentro de una función; la
# declaración va a ámbito de archivo y la llamada queda limpia.
P.append(("runtime/src/host_cpu_baseline.cpp",
r'''#if defined(MKW_UWP)
    { extern "C" void MkwUwpTrace(const char*); MkwUwpTrace(message.data); }
#endif''',
r'''#if defined(MKW_UWP)
    MkwUwpTrace(message.data);
#endif''', 1))

P.append(("runtime/src/host_cpu_baseline.cpp",
r'''[[noreturn]] void ReportUnsupportedCpu(const char* missing) {''',
r'''#if defined(MKW_UWP)
extern "C" void MkwUwpTrace(const char*);  // uwp_main.cpp
#endif
[[noreturn]] void ReportUnsupportedCpu(const char* missing) {''', 1))

P.append(("runtime/src/main.cpp",
r'''#if defined(MKW_UWP)
        { extern "C" void MkwUwpTrace(const char*); MkwUwpTrace(message.c_str()); }
#endif''',
r'''#if defined(MKW_UWP)
        MkwUwpTrace(message.c_str());
#endif''', 1))

P.append(("runtime/src/main.cpp",
r'''#include "abi_bridge.h"''',
r'''#if defined(MKW_UWP)
extern "C" void MkwUwpTrace(const char*);  // uwp_main.cpp
#endif
#include "abi_bridge.h"''', 1))

# ---------------- aurora-main ----------------
P.append(("aurora-main/lib/logging.cpp",
r'''#if defined(_WIN32)
    ::MessageBoxA(nullptr, body.c_str(), "Aurora fatal error",''',
r'''#if defined(_WIN32) && !defined(AURORA_WINDOWS_STORE)
    ::MessageBoxA(nullptr, body.c_str(), "Aurora fatal error",''', 1))

P.append(("aurora-main/lib/window.cpp",
r'''#if defined(_WIN32)
WNDPROC g_prevWindowProc = nullptr;''',
r'''#if defined(_WIN32) && !defined(AURORA_WINDOWS_STORE)
WNDPROC g_prevWindowProc = nullptr;''', 1))

P.append(("aurora-main/lib/window.cpp",
r'''#if defined(_WIN32)
  const uint64_t cached = g_nativeClientSize.load(std::memory_order_acquire);''',
r'''#if defined(_WIN32) && !defined(AURORA_WINDOWS_STORE)
  const uint64_t cached = g_nativeClientSize.load(std::memory_order_acquire);''', 1))

P.append(("aurora-main/lib/window.cpp",
r'''#if defined(_WIN32)
  install_window_proc_hook();''',
r'''#if defined(_WIN32) && !defined(AURORA_WINDOWS_STORE)
  install_window_proc_hook();''', 1))

P.append(("aurora-main/lib/window.cpp",
r'''#if defined(_WIN32)
  uninstall_window_proc_hook();''',
r'''#if defined(_WIN32) && !defined(AURORA_WINDOWS_STORE)
  uninstall_window_proc_hook();''', 1))

P.append(("aurora-main/lib/dawn/BackendBinding.cpp",
r'''#elif defined(SDL_PLATFORM_WIN32)
  std::shared_ptr<wgpu::SurfaceSourceWindowsHWND> desc = std::make_shared<wgpu::SurfaceSourceWindowsHWND>();''',
r'''#elif defined(SDL_PLATFORM_WINRT)
  // UWP/Xbox: la ventana de SDL3-uwp es una CoreWindow; Dawn (D3D12) la acepta directamente.
  std::shared_ptr<wgpu::SurfaceDescriptorFromWindowsCoreWindow> desc =
      std::make_shared<wgpu::SurfaceDescriptorFromWindowsCoreWindow>();
  desc->coreWindow = SDL_GetPointerProperty(props, SDL_PROP_WINDOW_WINRT_WINDOW_POINTER, nullptr);
  return std::move(desc);
#elif defined(SDL_PLATFORM_WIN32)
  std::shared_ptr<wgpu::SurfaceSourceWindowsHWND> desc = std::make_shared<wgpu::SurfaceSourceWindowsHWND>();''', 1))

P.append(("aurora-main/lib/input.cpp",
r'''  ASSERT(SDL_Init(SDL_INIT_HAPTIC | SDL_INIT_JOYSTICK | SDL_INIT_GAMEPAD), "Failed to initialize SDL subsystems: {}",
         SDL_GetError());''',
r'''#if defined(AURORA_WINDOWS_STORE)
  ASSERT(SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMEPAD), "Failed to initialize SDL subsystems: {}", SDL_GetError());
#else
  ASSERT(SDL_Init(SDL_INIT_HAPTIC | SDL_INIT_JOYSTICK | SDL_INIT_GAMEPAD), "Failed to initialize SDL subsystems: {}",
         SDL_GetError());
#endif''', 1))


# ---------------- Brawl: primera tanda ----------------

# vi.cpp: DWM_TIMING_INFO vive tras WINAPI_PARTITION_DESKTOP, asi que en la familia APP no existe.
# Hay un #else que deja d.valid en false: el juego se queda con su propio reloj, como en Linux.
P.append(("runtime/src/hle/vi.cpp",
r"""#if defined(_WIN32)
    using GetTimingFn = HRESULT(WINAPI*)(HWND, DWM_TIMING_INFO*);""",
r"""#if defined(_WIN32) && !defined(MKW_UWP)  /* UWP: sin DWM; el juego se queda con su reloj */
    using GetTimingFn = HRESULT(WINAPI*)(HWND, DWM_TIMING_INFO*);""", 1))

# game_folder.cpp: shobjidl.h no compila en la familia APP (su propio encabezado se rompe), y el
# selector de carpetas no tiene sentido en la consola: la ruta del disco va en el Config.toml.
P.append(("runtime/src/game_folder.cpp",
r"""#include <windows.h>
#include <shobjidl.h>""",
r"""#include <windows.h>
#if !defined(MKW_UWP)  /* UWP: shobjidl no compila en la familia APP */
#include <shobjidl.h>
#endif""", 1))

P.append(("runtime/src/game_folder.cpp",
r"""fs::path PickFolder() {
    fs::path result;""",
r"""fs::path PickFolder() {
    fs::path result;
#if !defined(MKW_UWP)  /* UWP: no hay selector de carpetas; la ruta la pone el Config.toml */""", 1))

P.append(("runtime/src/game_folder.cpp",
r"""    if (SUCCEEDED(init)) {
        CoUninitialize();
    }
    return result;""",
r"""    if (SUCCEEDED(init)) {
        CoUninitialize();
    }
#endif
    return result;""", 1))

# engine_loader.cpp: en el AppContainer solo se cargan las DLL del paquete, y por nombre.
P.append(("runtime/src/product/engine_loader.cpp",
r"""    HMODULE engine = LoadLibraryExW(module.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);""",
r"""#if defined(MKW_UWP)
    // UWP: el AppContainer carga solo DLL del propio paquete, y por nombre y no por ruta.
    HMODULE engine = LoadPackagedLibrary(module.filename().c_str(), 0);
#else
    HMODULE engine = LoadLibraryExW(module.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
#endif""", 1))

P.append(("runtime/src/product/engine_loader.cpp",
r"""        MessageBoxW(nullptr, message.c_str(), L"Super Smash Bros. Brawl", MB_OK | MB_ICONERROR);""",
r"""#if defined(MKW_UWP)
        // UWP: no hay MessageBox en la familia APP. Al depurador, que es lo que se puede leer
        // desde el Device Portal cuando la app muere sin pintar nada.
        ::OutputDebugStringW(message.c_str());
#else
        MessageBoxW(nullptr, message.c_str(), L"Super Smash Bros. Brawl", MB_OK | MB_ICONERROR);
#endif""", 1))

# sampling_profiler.cpp: CreateToolhelp32Snapshot y THREADENTRY32 no estan en la familia APP. El
# perfilador por muestreo solo se enciende con su variable de entorno, asi que en consola sobra.
P.append(("runtime/src/hle/sampling_profiler.cpp",
r"""#ifdef _WIN32
    static bool started = false;""",
r"""#if defined(_WIN32) && !defined(MKW_UWP)  /* UWP: sin Toolhelp32; no hay perfilador en consola */
    static bool started = false;""", 1))

# netplay_lobby.cpp: el AppContainer no lanza procesos hijos, asi que no hay CLI de Tailscale.
P.append(("runtime/src/netplay/netplay_lobby.cpp",
r"""std::string TailscaleStatusJson(const wchar_t* commandLine) {
    std::wstring cmd = commandLine;""",
r"""std::string TailscaleStatusJson(const wchar_t* commandLine) {
#if defined(MKW_UWP)
    // UWP: el AppContainer no lanza procesos hijos; no hay tailscale.exe que consultar.
    (void)commandLine;
    return {};
#else
    std::wstring cmd = commandLine;""", 1))

P.append(("runtime/src/netplay/netplay_lobby.cpp",
r"""    CloseHandle(readPipe);
    return json;
}""",
r"""    CloseHandle(readPipe);
    return json;
#endif
}""", 1))

# network_ssl.cpp: ssize_t y MSG_NOSIGNAL son POSIX. llvm-mingw los traia; el ABI de MSVC no, y
# en Winsock no hay SIGPIPE que silenciar.
P.append(("runtime/src/hle/net/network_ssl.cpp",
r"""#include <chrono>
#include <cstring>
#include <filesystem>
#include <optional>""",
r"""#include <chrono>
#include <cstddef>
#include <cstring>
#include <filesystem>
#include <optional>

#if defined(MKW_UWP)
// UWP: el ABI de MSVC no trae estos dos de POSIX. En Winsock no existe SIGPIPE, asi que la
// bandera que lo silencia no hace falta.
using ssize_t = std::ptrdiff_t;
#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0
#endif
#endif""", 1))


# ---------------- Brawl: segunda tanda, lo que destapo el compile-check ----------------

# main.cpp y host_cpu_baseline.cpp: nada que hacer aqui. Los parches del bloque «runtime» de mas
# arriba ya mueven la declaracion de MkwUwpTrace a ambito de archivo y dejan la llamada limpia;
# sale bien siempre que se apliquen de UNA pasada sobre un arbol limpio. Aplicarla sobre un arbol ya parcheado duplica el
# bloque y rompe la sintaxis (extern "C" no cabe dentro de una funcion).

# game_folder.cpp: el segundo MessageBoxW, el del bucle que pide la carpeta. El bloque ya tiene
# un #else con «return true» (la app eligio y comprobo la carpeta), que es justo lo que vale en la
# consola: la ruta del disco la pone el Config.toml del LocalState.
P.append(("runtime/src/game_folder.cpp",
r"""#if defined(_WIN32)
    std::wstring message = kSteps;""",
r"""#if defined(_WIN32) && !defined(MKW_UWP)  /* UWP: la ruta del disco la pone el Config.toml */
    std::wstring message = kSteps;""", 1))

# engine_loader.cpp: cpuid.h es de GCC y con el ABI de MSVC choca con intrin.h (clang declara
# __cpuid en los dos). __cpuid_count se escribe con el __cpuidex de intrin.h.
P.append(("runtime/src/product/engine_loader.cpp",
r"""#include <windows.h>
#include <cpuid.h>""",
r"""#include <windows.h>
#if defined(MKW_UWP)
// UWP/ABI de MSVC: cpuid.h es de GCC y choca con intrin.h, que es el que trae el cpuid aqui.
#include <intrin.h>
#define __cpuid_count(leaf, sub, a, b, c, d)                                   \
    do {                                                                       \
        int mkw_regs_[4];                                                      \
        __cpuidex(mkw_regs_, static_cast<int>(leaf), static_cast<int>(sub));    \
        (a) = mkw_regs_[0];                                                     \
        (b) = mkw_regs_[1];                                                     \
        (c) = mkw_regs_[2];                                                     \
        (d) = mkw_regs_[3];                                                     \
    } while (0)
#else
#include <cpuid.h>
#endif""", 1))


# ---------------- Brawl: network_ssl.cpp, la tercera rama ----------------

# Los campos de la sesion: en UWP no hay ni Schannel ni mbed TLS.
P.append(("runtime/src/hle/net/network_ssl.cpp",
r"""#else
    bool haveSsl = false;
    mbedtls_ssl_context sslContext{};
    mbedtls_ssl_config sslConfig{};
    mbedtls_net_context netContext{};
#endif""",
r"""#elif defined(MKW_UWP)
    // UWP: ni Schannel (no esta en la familia APP) ni mbed TLS (sus cabeceras solo entran con
    // #ifndef _WIN32, y del arbol solo viene el pin de la dependencia).
    bool haveSsl = false;
#else
    bool haveSsl = false;
    mbedtls_ssl_context sslContext{};
    mbedtls_ssl_config sslConfig{};
    mbedtls_net_context netContext{};
#endif""", 1))

# Las implementaciones: los stubs que dejan el SSL apagado sin tocar a quien lo llama.
P.append(("runtime/src/hle/net/network_ssl.cpp",
r"""    return copied == 0 ? SSL_ERR_ZERO : static_cast<int32_t>(copied);
}
#else
// Windows gets TLS for free from the OS (Schannel, above) - mbed TLS is this project's own""",
r"""    return copied == 0 ? SSL_ERR_ZERO : static_cast<int32_t>(copied);
}
#elif defined(MKW_UWP)
// UWP: sin Schannel y sin mbed TLS, el SSL del juego queda desactivado. En la consola no se
// pierde nada: Nintendo WFC cerro en 2014, y lo que si se usa del modulo de red (los sockets en
// claro) no pasa por aqui.
static void ClearSslSession(SslSession& ssl) {
    ssl = {};
}

static int32_t SslHandshakeImpl(SslSession&) {
    return SSL_ERR_FAILED;
}

static int32_t SslWrite(SslSession&, const uint8_t*, uint32_t) {
    return SSL_ERR_FAILED;
}

static int32_t SslRead(SslSession&, uint8_t*, uint32_t) {
    return SSL_ERR_FAILED;
}
#else
// Windows gets TLS for free from the OS (Schannel, above) - mbed TLS is this project's own""", 1))

# El timeout de los sockets es de Winsock, no de Schannel: en UWP vale la rama de Windows (un
# DWORD de milisegundos), no la de POSIX (struct timeval).
P.append(("runtime/src/hle/net/network_ssl.cpp",
r"""#if defined(_WIN32) && !defined(MKW_UWP)  /* UWP: sin Schannel, usa los stubs de abajo */
        const int timeoutMs = 15000;""",
r"""#if defined(_WIN32)  /* el timeout es de Winsock y no de Schannel: vale igual en UWP */
        const int timeoutMs = 15000;""", 1))


# ---------------- Brawl: el indexado del disco en el AppContainer ----------------

# fs::relative() canonicaliza contra el disco (GetFinalPathNameByHandle) y el AppContainer de la
# consola lo rechaza: da error para CADA archivo, el indice del DVD queda en 0 y el juego muere
# con PPCHalt al pedir el primero. lexically_relative es puramente lexico y no toca el disco.
P.append(("runtime/src/hle/storage/dvd.cpp",
r"""        const fs::path relative = fs::relative(entry.path(), root, entryEc);
        if (entryEc) {
            return;
        }""",
r"""#if defined(MKW_UWP)
        // UWP: fs::relative() canonicaliza contra el disco y el AppContainer lo rechaza, asi que
        // el indice del DVD saldria con 0 archivos. Lexico y sin tocar el disco:
        const fs::path relative = entry.path().lexically_relative(root);
        if (relative.empty()) {
            return;
        }
#else
        const fs::path relative = fs::relative(entry.path(), root, entryEc);
        if (entryEc) {
            return;
        }
#endif""", 1))


def main() -> int:
    fallos = 0
    tocados = set()
    for rel, viejo, nuevo, n in P:
        p = PORT / rel
        texto = p.read_text(encoding="utf-8")
        # Idempotencia: si el texto nuevo ya está, el parche se aplicó (aunque el viejo siga
        # apareciendo dentro del nuevo, como pasa con los que solo envuelven una línea en #if).
        if nuevo in texto:
            print(f"[ya]  {rel}: {viejo.splitlines()[0][:60]!r}")
            continue
        c = texto.count(viejo)
        if c != n:
            print(f"[MAL] {rel}: esperado {n}, hay {c}: {viejo.splitlines()[0][:70]!r}")
            fallos += 1
            continue
        p.write_text(texto.replace(viejo, nuevo), encoding="utf-8", newline="\n")
        tocados.add(rel)
        print(f"[ok]  {rel}: {viejo.splitlines()[0][:60]!r} x{n}")
    print(f"archivos tocados: {len(tocados)}  fallos: {fallos}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
