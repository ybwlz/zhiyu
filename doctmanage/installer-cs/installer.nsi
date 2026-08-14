; 知屿安装器 - NSIS 静默自解压外壳
Name "知屿安装器"
OutFile "知屿安装器.exe"
SilentInstall silent
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 64
Unicode true
AutoCloseWindow true

Section
  SetOutPath "$TEMP\zhiyu-installer"
  File /r "bin\Release\net8.0-windows\win-x64\publish\*.*"
  ExecWait '"$TEMP\zhiyu-installer\知屿安装器.exe"'
  RMDir /r "$TEMP\zhiyu-installer"
SectionEnd