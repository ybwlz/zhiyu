@echo off
cd /d "%~dp0"
windres resource.rc -O coff -o resource.o
g++ main.cpp resource.o -o 知屿安装器.exe -ld2d1 -ldwrite -ldwmapi -ld3d11 -ldxgi -ldcomp -lole32 -lshell32 -luuid -lgdi32 -luser32 -municode -mwindows -O2 -static
echo DONE
