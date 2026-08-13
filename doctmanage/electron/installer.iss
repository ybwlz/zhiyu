; 知屿 Windows 安装器脚本（Inno Setup 6）
; 源：release\知屿-win32-x64\  输出：release\知屿-setup.exe
#define MyAppName "知屿"
#define MyAppVersion "1.2.0"
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
ArchitecturesInstallIn64BitMode=x64compatible
; 未签名安装包，不写 SignedUninstaller
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "..\release\知屿-win32-x64\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动知屿"; Flags: nowait postinstall skipifsilent
