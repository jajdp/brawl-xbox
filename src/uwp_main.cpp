// Punto de entrada del port UWP (Xbox Series X, Dev Mode) de Super Smash Bros. Brawl,
// sobre el runtime de WiiCompiled.
//
// En UWP el proceso arranca por CoreApplication, no por main(): SDL3-uwp (SternXD) trae ese
// cascarón dentro de SDL_RunApp, que crea la CoreWindow y llama a la función de la app en su
// propio hilo. Ahí se entra al runtime de Wiicompiled tal cual (RuntimeMain, en main.cpp), que
// bajo MKW_UWP no define main(). Mismo esquema que platforms/uwp/main.cpp de Dusklight.
#include <windows.h>

#include <SDL3/SDL.h>
#define SDL_MAIN_HANDLED
#include <SDL3/SDL_main.h>

#include <cstdio>
#include <string>

int RuntimeMain(int argc, char** argv);

// Traza de arranque en la carpeta temporal del paquete (\AC\Temp, visible por el Device Portal):
// en la consola no hay consola ni depurador, y el runtime solo abre su propio registro más tarde.
extern "C" void MkwUwpTrace(const char* texto) {
    wchar_t tmp[MAX_PATH]{};
    GetTempPathW(MAX_PATH, tmp);
    const std::wstring ruta = std::wstring(tmp) + L"brawl-uwp-traza.txt";
    HANDLE h = CreateFile2(ruta.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ, OPEN_ALWAYS, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    const std::string linea = std::string(texto) + "\r\n";
    DWORD escrito = 0;
    WriteFile(h, linea.data(), static_cast<DWORD>(linea.size()), &escrito, nullptr);
    CloseHandle(h);
}

#include <filesystem>
#include <fstream>

// Sonda de diagnóstico: ¿puede el AppContainer leer los assets que dejó el Device Portal en
// LocalState\GameAssets\DATA? Escribe el resultado en LocalState\WiiCompiled\uwp-sonda.txt.
static void MkwUwpProbeAssets() {
    char* pref = SDL_GetPrefPath(nullptr, "WiiCompiled");
    if (pref == nullptr) return;
    const std::filesystem::path userData(pref);
    SDL_free(pref);
    std::ofstream out(userData / "uwp-sonda.txt", std::ios::trunc);

    // Espacio del almacenamiento donde vive el LocalState. El Device Portal NO lo informa por
    // ninguna ruta (/api/os/storage, /ext/storage y companía dan 404), y en Dev Mode no es el
    // disco entero de la consola: es una particion propia del espacio de desarrollo.
    // (los nombres llevan sufijo: mas abajo esta funcion ya usa un `total` que es un int)
    ULARGE_INTEGER discoDisponible{}, discoTotal{}, discoLibre{};
    if (GetDiskFreeSpaceExW(userData.wstring().c_str(), &discoDisponible, &discoTotal, &discoLibre)) {
        out << "LocalState: libre " << (discoDisponible.QuadPart / 1048576) << " MiB de "
            << (discoTotal.QuadPart / 1048576) << " MiB\n";
    } else {
        out << "LocalState: GetDiskFreeSpaceExW fallo, GetLastError=" << GetLastError() << "\n";
    }
    wchar_t tmpDir[MAX_PATH]{};
    if (GetTempPathW(MAX_PATH, tmpDir) &&
        GetDiskFreeSpaceExW(tmpDir, &discoDisponible, &discoTotal, &discoLibre)) {
        out << "AC\\Temp:    libre " << (discoDisponible.QuadPart / 1048576) << " MiB de "
            << (discoTotal.QuadPart / 1048576) << " MiB\n";
    }

    const std::filesystem::path root = (userData / ".." / "GameAssets" / "DATA").lexically_normal();
    std::error_code ec;
    out << "raiz: " << root.string() << "\n";
    out << "exists: " << std::filesystem::exists(root, ec) << " ec=" << ec.message() << "\n";
    out << "is_directory: " << std::filesystem::is_directory(root, ec) << " ec=" << ec.message() << "\n";
    ec.clear();
    std::filesystem::directory_iterator it(root, std::filesystem::directory_options::none, ec);
    out << "directory_iterator ec=" << ec.value() << " (" << ec.message() << ")\n";
    int n = 0;
    for (const auto& e : it) { out << "  " << e.path().filename().string() << "\n"; if (++n > 12) break; }
    ec.clear();
    std::filesystem::recursive_directory_iterator rit(root, std::filesystem::directory_options::none, ec);
    out << "recursive ec=" << ec.value() << " (" << ec.message() << ")\n";
    int total = 0;
    for (auto i = rit; i != std::filesystem::recursive_directory_iterator(); i.increment(ec)) { if (ec) { out << "  increment ec=" << ec.message() << "\n"; break; } ++total; }
    out << "entradas recursivas: " << total << "\n";
    std::ifstream fst(root / "sys" / "fst.bin", std::ios::binary);
    out << "sys/fst.bin ifstream: " << (fst.is_open() ? "abierto" : "NO abre") << "\n";
    HANDLE h = CreateFile2((root / "sys" / "fst.bin").wstring().c_str(), GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING, nullptr);
    out << "sys/fst.bin CreateFile2: " << (h != INVALID_HANDLE_VALUE ? "abierto" : "NO abre") << " GetLastError=" << GetLastError() << "\n";
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    out.close();
}

static int MkwUwpBootstrap(int argc, char** argv) {
    MkwUwpTrace("bootstrap: dentro de SDL_RunApp, llamando a RuntimeMain");
    MkwUwpProbeAssets();
    // Windows.Gaming.Input para los mandos de la consola (SDL3-uwp lo trae opcional).
    SDL_SetHint(SDL_HINT_JOYSTICK_WGI, "true");
    SDL_SetHint(SDL_HINT_ENABLE_SCREEN_KEYBOARD, "true");
    const int rc = RuntimeMain(argc, argv);
    MkwUwpTrace((std::string("RuntimeMain devolvio ") + std::to_string(rc)).c_str());
    return rc;
}

int CALLBACK WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    MkwUwpTrace("WinMain: proceso vivo (los inicializadores estaticos ya corrieron)");
    return SDL_RunApp(0, nullptr, MkwUwpBootstrap, nullptr);
}
