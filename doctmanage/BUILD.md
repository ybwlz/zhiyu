# 知屿 · 打包发布指南（Windows 桌面版）

> 在项目根 `documentplatform/doctmanage` 目录下执行。所有命令都是 PowerShell 语法。

## 一、日常前端改动（网页版 + 桌面版共用）

改完代码后构建（**每次必做**，很快，十几秒）：

```powershell
npm run build
```

> 说明：默认 `base: '/zhiyu/'`，产出给网页版（服务器 `/zhiyu/` 子路径）。

---

## 二、桌面版（Electron）打包

### 方式 A：快方案（只更新前端/主进程，2 分钟，推荐日常用）

Electron 运行时用的是 `release\知屿-win32-x64\resources\app\` 里的文件，
只更新这几样就能让 exe 用上新代码（**不需要完整重打包**）：

```powershell
# 1. 构建桌面版前端产物（相对路径 base）
npx vite build --base=./ --outDir dist-electron

# 2. 覆盖 exe 运行目录（前端产物 + 主进程 + 版本号）
$app = "release\知屿-win32-x64\resources\app"
Copy-Item dist-electron\* $app\dist-electron\ -Recurse -Force
Copy-Item electron\main.cjs, electron\preload.cjs $app\electron\ -Force
Copy-Item package.json $app\package.json -Force
```

### 方式 B：完整重打包（几十分钟，改了图标/需要全新目录时用）

```powershell
npx electron-packager . 知屿 --platform=win32 --arch=x64 --out=release --overwrite --icon=electron/icon.ico --ignore=^/node_modules$ --ignore=^/src --ignore=^/dist$ --ignore=^/release --ignore=^/docs
```

> 这一步很慢（复制依赖 + 打资源），会覆盖 `release\知屿-win32-x64\`。

### 方式 C：改 exe 图标（不重新打包）

```powershell
node_modules\rcedit\bin\rcedit-x64.exe "release\知屿-win32-x64\知屿.exe" --set-icon "electron\icon.ico"
```

---

## 三、安装器（setup.exe）

用本机已装的 **Inno Setup 6**（ISCC 命令行编译器）：

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" electron\installer.iss
```

产出：`release\知屿-setup.exe`（约 90MB）。

> 脚本在 `electron/installer.iss`，改了版本号/应用名只需改里面的 `MyAppVersion` 等常量。

---

## 四、绿色版 zip

```powershell
Compress-Archive -Path release\知屿-win32-x64\* -DestinationPath release\zhiyu-win32-x64.zip -Force
```

---

## 五、发版：更新服务器版本号（自动更新检查用）

桌面版启动时会读取服务器 `/downloads/version.json`，**版本号大于本地就提示更新**。

发版流程：
1. 改 `package.json` 的 `version`（比如 `1.3.0`）——这是**本地版本号**（快方案里已拷进 app）
2. 重新打包 zip / setup（上面第二/三/四步）
3. 上传产物到服务器：
   - `release\zhiyu-win32-x64.zip` → `/www/wwwroot/zhiyu/downloads/`
   - `release\知屿-setup.exe` → `/www/wwwroot/zhiyu/downloads/`
4. 更新 `/www/wwwroot/zhiyu/downloads/version.json`：
   ```json
   {
     "version": "1.3.0",
     "notes": "本次更新内容，一句话",
     "url": "http://www.zhiyur.cn/downloads/zhiyu-win32-x64.zip",
     "date": "2026-08-13"
   }
   ```
5. 用户重启桌面版 → 自动检测到新版本 → 右下角提示「立即下载」

> 上传服务器用 SSH/SFTP（`root@182.254.209.123`，`/www/wwwroot/zhiyu/downloads/`）或用宝塔文件管理。

---

## 常用命令速查

| 目的 | 命令 |
| --- | --- |
| 前端构建（网页版） | `npm run build` |
| 桌面版前端构建 | `npx vite build --base=./ --outDir dist-electron` |
| 快方案更新 exe | 见「二、方式 A」3 条 Copy |
| 完整重打包 | 见「二、方式 B」 |
| 编译安装器 | `& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" electron\installer.iss` |
| 打 zip | `Compress-Archive -Path release\知屿-win32-x64\* -DestinationPath release\zhiyu-win32-x64.zip -Force` |
| 本地验证 exe | `release\知屿-win32-x64\知屿.exe`（双击） |
