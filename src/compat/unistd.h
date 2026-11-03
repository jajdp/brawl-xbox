// Puente de <unistd.h> para compilar zlib con el ABI de MSVC.
//
// El zconf.h que CMake genero para zlib (native-build/_deps/zlib-build/zconf.h) lo configuro
// llvm-mingw, que SI tiene <unistd.h>, asi que deja Z_HAVE_UNISTD_H activo y en su linea 494 hace
// el include. Al recompilar con --target=x86_64-pc-windows-msvc esa cabecera no existe y las 15
// unidades de zlib mueren con «'unistd.h' file not found».
//
// En lugar de regenerar el zconf.h (que obligaria a reconfigurar el arbol de PC entero, y ese
// arbol es el que da la base de compilacion), se le pone este puente delante con un -I propio
// para los archivos de zlib. io.h trae read, write, close y lseek, que es todo lo que zlib usa de
// POSIX (gzread/gzwrite sobre descriptores).
//
// Se le pasa solo a Dependencies/zlib: ver compile_check.py.

#pragma once

#include <io.h>
#include <process.h>
