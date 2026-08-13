; 知屿 Windows 安装器脚本（Inno Setup 6）
; 源：release\知屿-win32-x64\  输出：release\知屿-setup.exe
#define MyAppName "知屿"
#define MyAppVersion "1.8.0"
#define MyAppExeName "知屿.exe"
#define MyAppId "{{8E3D1A2C-5B4F-4E6D-9A7B-1C2D3E4F5A6B}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=知屿
AppPublisherURL=http://www.zhiyur.cn/zhiyu/
AppSupportURL=http://www.zhiyur.cn/zhiyu/
DefaultDirName={autopf}\知屿
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=..\release
OutputBaseFilename=知屿-setup
SetupIconFile=..\electron\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardImageFile=..\electron\wizard-image.jpg
WizardSmallImageFile=..\electron\wizard-small.jpg
DisableDirPage=no
ArchitecturesInstallIn64BitMode=x64compatible
; 未签名安装包，不写 SignedUninstaller
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Messages]
SetupWindowTitle=知屿 安装程序
WelcomeLabel1=欢迎安装知屿
WelcomeLabel2=知屿 —— 把散落的笔记、截图与灵感，汇成一座属于自己的知识岛。%n%n点击「下一步」开始安装（建议勾选「开机自启动」）。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："
Name: "autostart"; Description: "开机自启动（登录 Windows 后自动运行知屿）"; GroupDescription: "附加任务："

[Files]
Source: "..\release\知屿-win32-x64\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; 开机自启动（勾选时写入，卸载时自动删除）
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "知屿"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动知屿"; Flags: nowait postinstall skipifsilent
