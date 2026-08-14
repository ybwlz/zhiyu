# 手动打包知屿安装器（用本地 electron，不下载）
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\50534\Desktop\桌面整理\文件夹归档\项目代码\document\documentplatform\doctmanage'
$elecDist = "$root\node_modules\electron\dist"
$inst = "$root\installer"
$out = "$inst\dist\知屿安装器-win32-x64"
$appDir = "$out\resources\app"

# 1. 复制 electron 运行环境
Write-Output '复制 electron 运行时…'
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Path $out -Force | Out-Null
Copy-Item "$elecDist\*" $out -Recurse -Force

# 2. 复制 app（main/preload/renderer/package.json）
Write-Output '复制 app…'
New-Item -ItemType Directory -Path $appDir -Force | Out-Null
Copy-Item "$inst\main.cjs", "$inst\preload.cjs", "$inst\package.json" $appDir -Force
Copy-Item "$inst\renderer" $appDir -Recurse -Force

# 3. 内嵌绿色版（extraResource）
Write-Output '复制绿色版（215MB，稍等）…'
Copy-Item "$root\release\知屿-win32-x64" "$out\resources\知屿-win32-x64" -Recurse -Force

# 托盘图标（主程序 resources/icon.ico）
Copy-Item "$inst\icon.ico" "$out\resources\icon.ico" -Force

# 编译 Go 卸载器（已弃用：卸载入口改为硬链接主程序 exe → 知屿卸载.exe，进 Electron 卸载模式）
# Write-Output '编译卸载器（Go 2MB）…'
# pushd "$root\uninstaller"
# go build -ldflags "-s -w -H windowsgui" -o "$out\resources\zhiyu-uninstaller.exe" .
# popd

# 4. exe 图标（rcedit）+ 改名
Write-Output '设置图标…'
$rcedit = "$root\node_modules\rcedit\bin\rcedit-x64.exe"
if (Test-Path $rcedit) {
  & $rcedit "$out\electron.exe" --set-icon "$inst\icon.ico" | Out-Null
}
Rename-Item "$out\electron.exe" '知屿安装器.exe'

Write-Output '打包完成'
Get-Item "$out\知屿安装器.exe" | Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,1)}}
(Get-ChildItem $out -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB | ForEach-Object { Write-Output ("总大小: {0} MB" -f [math]::Round($_,0)) }
