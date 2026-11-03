// Ejecutable minimo para la SEMILLA del paquete.
//
// La primera instalacion de una familia nueva en la la consola va a D:\DevelopmentFiles,
// que son 5 GB casi llenos, y el portal responde «There is not enough space on the disk»
// (-2147024784). Las ACTUALIZACIONES de una familia ya registrada van a otro almacenamiento y
// entran sin problema.
//
// Asi que primero se instala esta semilla —la misma identidad, version 0.1.0.0, el manifiesto y
// los mosaicos de verdad y este exe de unos pocos KB— y despues el paquete completo como
// actualizacion (0.1.0.1). La semilla no tiene que funcionar: solo registrar la familia.

#include <windows.h>

int CALLBACK WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    return 0;
}
