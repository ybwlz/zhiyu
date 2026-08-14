using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Microsoft.Win32;

namespace ZhiyuInstaller;

public partial class MainWindow : Window
{
    private string _greenDir = "";
    private string _targetDir = "";
    private string _theme = "starlight";
    private string _installRoot = "";
    private string _lastError = "";

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CreateHardLink(string lpFileName, string lpExistingFileName, IntPtr lpSecurityAttributes);

    [DllImport("user32.dll")]
    private static extern int GetWindowLong(IntPtr hWnd, int nIndex);
    [DllImport("user32.dll")]
    private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

    public MainWindow()
    {
        InitializeComponent();
        Loaded += OnLoaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        EnableMinimizeBox();
        _greenDir = FindGreenDir();
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        TxtDir.Text = Path.Combine(local, "知屿");
        // 检测是否已安装（注册表 InstallLocation）
        using var key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿");
        var root = key?.GetValue("InstallLocation") as string;
        if (!string.IsNullOrEmpty(root) && Directory.Exists(root))
        {
            _installRoot = root;
            BtnUninstall.Visibility = Visibility.Visible;
        }
    }

    // 给无边框窗口加 WS_MINIMIZEBOX，让任务栏点击能最小化/还原
    private void EnableMinimizeBox()
    {
        const int GWL_STYLE = -16;
        const int WS_MINIMIZEBOX = 0x00020000;
        var hwnd = new System.Windows.Interop.WindowInteropHelper(this).Handle;
        if (hwnd == IntPtr.Zero) return;
        var style = GetWindowLong(hwnd, GWL_STYLE);
        SetWindowLong(hwnd, GWL_STYLE, style | WS_MINIMIZEBOX);
    }

    private static string FindGreenDir()
    {
        var dir = AppContext.BaseDirectory;
        // 1. exe 同目录的「知屿-win32-x64」（内嵌绿色版，随安装器分发）
        var local = Path.Combine(dir, "知屿-win32-x64");
        if (Directory.Exists(local) && File.Exists(Path.Combine(local, "知屿.exe")))
            return local;
        // 2. 向上查找 release\知屿-win32-x64（开发环境）
        for (int i = 0; i < 12; i++)
        {
            var candidate = Path.Combine(dir, "release", "知屿-win32-x64");
            if (Directory.Exists(candidate) && File.Exists(Path.Combine(candidate, "知屿.exe")))
                return candidate;
            var parent = Path.GetDirectoryName(dir);
            if (parent == null || parent == dir) break;
            dir = parent;
        }
        return "";
    }

    // ── 标题栏 ──
    private void TitleBar_OnMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ButtonState == MouseButtonState.Pressed) DragMove();
    }
    private void BtnMin_OnClick(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;
    private void BtnClose_OnClick(object sender, RoutedEventArgs e) => Close();

    // ── 页面切换 ──
    private void ShowPage(string name)
    {
        PageWelcome.Visibility = name == "welcome" ? Visibility.Visible : Visibility.Collapsed;
        PagePreview.Visibility = name == "preview" ? Visibility.Visible : Visibility.Collapsed;
        PageTheme.Visibility = name == "theme" ? Visibility.Visible : Visibility.Collapsed;
        PageConfig.Visibility = name == "config" ? Visibility.Visible : Visibility.Collapsed;
        PageProgress.Visibility = name == "progress" ? Visibility.Visible : Visibility.Collapsed;
        PageDone.Visibility = name == "done" ? Visibility.Visible : Visibility.Collapsed;
        PageUninstall.Visibility = name == "uninstall" ? Visibility.Visible : Visibility.Collapsed;
    }

    private void BtnStart_OnClick(object sender, RoutedEventArgs e) => ShowPage("preview");
    private void BtnPvBack_OnClick(object sender, RoutedEventArgs e) => ShowPage("welcome");
    private void BtnPvNext_OnClick(object sender, RoutedEventArgs e) => ShowPage("theme");
    private void BtnThBack_OnClick(object sender, RoutedEventArgs e) => ShowPage("preview");
    private void BtnThNext_OnClick(object sender, RoutedEventArgs e) => ShowPage("config");
    private void BtnConfigBack_OnClick(object sender, RoutedEventArgs e) => ShowPage("theme");

    // ── 主题选择 ──
    private void PickTheme(object sender, MouseButtonEventArgs e)
    {
        if (sender is Border b && b.Tag is string tag) _theme = tag;
        HighlightTheme();
    }
    private void HighlightTheme()
    {
        RowStarlight.BorderBrush = _theme == "starlight" ? new SolidColorBrush(Color.FromRgb(59, 130, 246)) : Brushes.Transparent;
        RowSky.BorderBrush = _theme == "sky" ? new SolidColorBrush(Color.FromRgb(59, 130, 246)) : Brushes.Transparent;
        RowMinimal.BorderBrush = _theme == "minimal" ? new SolidColorBrush(Color.FromRgb(59, 130, 246)) : Brushes.Transparent;
    }

    // ── 浏览目录 ──
    private void BtnBrowse_OnClick(object sender, RoutedEventArgs e)
    {
        var dlg = new Microsoft.Win32.OpenFolderDialog
        {
            Title = "选择安装位置",
            InitialDirectory = string.IsNullOrEmpty(TxtDir.Text) ? null : TxtDir.Text,
        };
        if (dlg.ShowDialog() == true)
        {
            var clean = dlg.FolderName.TrimEnd('\\');
            TxtDir.Text = Path.GetFileName(clean) == "知屿" ? clean : clean + "\\知屿";
        }
    }

    // ── 条款弹窗 ──
    private const string TERMS = "一、账号与安全\n1. 你负责自己账号的安全，请勿共享密码，发现异常及时修改。\n2. 每个账号对应独立的笔记与数据，请妥善保管登录信息。\n\n二、内容与版权\n1. 你的笔记内容归你所有（私密笔记仅自己可见；公开笔记会展示在笔记广场）。\n2. 请勿发布违反法律法规、侵犯他人权益的内容。\n\n三、AI 助手\n1. AI 生成内容仅供参考，不构成任何专业建议。\n2. AI 使用计入免费额度，超出后可前往知屿币商城兑换。\n\n四、服务说明\n1. 知屿为云端服务，数据存储于服务器，请勿存放极端敏感信息。\n2. 服务可能调整或升级，我们会尽力提前通知。\n3. 完整条款见官网：www.zhiyur.cn。";
    private const string PRIVACY = "一、我们收集的信息\n1. 账号信息：用户名、邮箱（仅用于登录与找回）。\n2. 内容数据：你创建的笔记、收藏、批注。\n3. 使用日志：访问时间、操作记录（用于安全与优化）。\n\n二、信息的使用\n1. 仅用于提供、维护与改进知屿服务。\n2. 不会向任何第三方出售或出租你的数据。\n\n三、信息的存储与保护\n1. 数据加密存储于服务器，传输使用加密通道。\n2. 你可以随时删除自己的笔记与账号。\n\n四、你的权利\n1. 可随时导出或删除自己的数据。\n2. 对本协议有疑问可联系我们。\n3. 完整协议见官网：www.zhiyur.cn。";

    private void LinkTerms_OnClick(object sender, RoutedEventArgs e)
    {
        TermsTitle.Text = "服务条款";
        TermsBody.Text = TERMS;
        TermsModal.Visibility = Visibility.Visible;
    }
    private void LinkPrivacy_OnClick(object sender, RoutedEventArgs e)
    {
        TermsTitle.Text = "隐私协议";
        TermsBody.Text = PRIVACY;
        TermsModal.Visibility = Visibility.Visible;
    }
    private void BtnTermsClose_OnClick(object sender, RoutedEventArgs e) => TermsModal.Visibility = Visibility.Collapsed;
    private void TermsModal_OnClick(object sender, MouseButtonEventArgs e)
    {
        if (e.OriginalSource == TermsModal) TermsModal.Visibility = Visibility.Collapsed;
    }

    // ── 安装 ──
    private async void BtnInstall_OnClick(object sender, RoutedEventArgs e)
    {
        _targetDir = TxtDir.Text.Trim();
        if (string.IsNullOrEmpty(_targetDir)) return;
        var makeShortcut = ChkShortcut.IsChecked == true;
        var autoStart = ChkAutoStart.IsChecked == true;
        ShowPage("progress");
        var ok = await System.Threading.Tasks.Task.Run(() => DoInstall(makeShortcut, autoStart));
        Dispatcher.Invoke(() =>
        {
            if (ok) { DoneTxt.Text = "已安装到：" + _targetDir; ShowPage("done"); }
            else ProgressTxt.Text = "安装失败：" + _lastError;
        });
    }

    private bool DoInstall(bool makeShortcut, bool autoStart)
    {
        try
        {
            SetProgress(5, "准备安装目录…");
            Directory.CreateDirectory(_targetDir);

            // 从嵌入资源读 zip（优先），兜底磁盘 zip / 文件夹
            var asm = System.Reflection.Assembly.GetExecutingAssembly();
            Stream? zipStream = asm.GetManifestResourceStream("ZhiyuInstaller.zhiyu-green.zip");
            var zipPath = Path.Combine(AppContext.BaseDirectory, "zhiyu-green.zip");
            if (zipStream == null && File.Exists(zipPath))
                zipStream = File.OpenRead(zipPath);

            if (zipStream != null)
            {
                // 解压压缩包（带进度）
                SetProgress(8, "正在解压安装文件…");
                using (zipStream)
                using (var archive = new ZipArchive(zipStream, ZipArchiveMode.Read))
                {
                    int total = archive.Entries.Count, done = 0;
                    foreach (var entry in archive.Entries)
                    {
                        var dest = Path.Combine(_targetDir, entry.FullName.Replace('/', '\\'));
                        if (string.IsNullOrEmpty(entry.Name)) { Directory.CreateDirectory(dest); continue; }
                        Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
                        entry.ExtractToFile(dest, true);
                        done++;
                        if (done % 100 == 0 || done == total)
                            SetProgress(8 + (int)(done * 62.0 / total), "正在安装核心组件…");
                    }
                }
            }
            else if (Directory.Exists(_greenDir))
            {
                // 兜底：文件夹复制
                var files = Directory.GetFiles(_greenDir, "*", SearchOption.AllDirectories);
                int total = files.Length, done = 0;
                foreach (var f in files)
                {
                    var rel = Path.GetRelativePath(_greenDir, f);
                    var dest = Path.Combine(_targetDir, rel);
                    Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
                    File.Copy(f, dest, true);
                    done++;
                    if (done % 50 == 0 || done == total)
                        SetProgress(8 + (int)(done * 62.0 / total), "正在安装核心组件…");
                }
            }
            else
            {
                throw new Exception("安装资源缺失");
            }

            // 主题配置
            SetProgress(72, "写入主题配置…");
            var confDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "zhiyu");
            Directory.CreateDirectory(confDir);
            var themeName = _theme == "sky" ? "sky" : _theme == "minimal" ? "minimal" : "starlight";
            File.WriteAllText(Path.Combine(confDir, "config.json"), "{\"theme\":\"" + themeName + "\"}");

            if (makeShortcut)
            {
                SetProgress(78, "创建桌面快捷方式…");
                CreateShortcut();
            }
            if (autoStart)
            {
                SetProgress(84, "设置开机自启动…");
                SetAutoStart();
            }

            SetProgress(90, "创建卸载入口…");
            var appExe = Path.Combine(_targetDir, "知屿.exe");
            var unExe = Path.Combine(_targetDir, "知屿卸载.exe");
            if (File.Exists(appExe) && !File.Exists(unExe))
            {
                if (!CreateHardLink(unExe, appExe, IntPtr.Zero))
                    File.Copy(appExe, unExe);
            }

            SetProgress(95, "写入注册表…");
            RegisterUninstall();

            SetProgress(100, "安装完成");
            return true;
        }
        catch (Exception ex)
        {
            _lastError = ex.Message;
            Dispatcher.Invoke(() => ProgressTxt.Text = "失败：" + ex.Message);
            return false;
        }
    }

    private void SetProgress(int pct, string msg)
    {
        Dispatcher.Invoke(() =>
        {
            ProgressFill.Width = pct * 560 / 100.0;
            ProgressPct.Text = pct + "%";
            ProgressTxt.Text = msg;
        });
    }

    private void CreateShortcut()
    {
        var desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        var exe = Path.Combine(_targetDir, "知屿.exe");
        var lnk = Path.Combine(desktop, "知屿.lnk");
        var ps =
            "$ws = New-Object -ComObject WScript.Shell; " +
            $"$s = $ws.CreateShortcut('{lnk.Replace("'", "''")}'); " +
            $"$s.TargetPath = '{exe.Replace("'", "''")}'; " +
            $"$s.WorkingDirectory = '{_targetDir.Replace("'", "''")}'; " +
            "$s.Save()";
        var psi = new ProcessStartInfo("powershell.exe", $"-NoProfile -WindowStyle Hidden -Command \"{ps}\"")
        { UseShellExecute = false, CreateNoWindow = true };
        Process.Start(psi)?.WaitForExit(5000);
    }

    private void SetAutoStart()
    {
        using var key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run");
        key.SetValue("知屿", $"\"{Path.Combine(_targetDir, "知屿.exe")}\"");
    }

    private void RegisterUninstall()
    {
        using var key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿");
        key.SetValue("DisplayName", "知屿");
        key.SetValue("DisplayVersion", "1.2.0");
        key.SetValue("Publisher", "知屿");
        key.SetValue("InstallLocation", _targetDir);
        key.SetValue("UninstallString", $"\"{Path.Combine(_targetDir, "知屿卸载.exe")}\" --uninstall");
    }

    private void BtnLaunch_OnClick(object sender, RoutedEventArgs e)
    {
        // 启动主程序
        try
        {
            var exe = Path.Combine(_targetDir, "知屿.exe");
            if (File.Exists(exe))
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(exe) { UseShellExecute = true, WorkingDirectory = _targetDir });
        }
        catch { }
        Close();
    }
    private void BtnFinish_OnClick(object sender, RoutedEventArgs e) => Close();

    // ── 卸载 ──
    private void BtnUninstall_OnClick(object sender, RoutedEventArgs e)
    {
        UninstallDirTxt.Text = "将删除 " + _installRoot + " 下的程序、桌面快捷方式与开机自启项。";
        ShowPage("uninstall");
    }
    private void BtnUninstallCancel_OnClick(object sender, RoutedEventArgs e) => ShowPage("welcome");

    private async void BtnUninstallGo_OnClick(object sender, RoutedEventArgs e)
    {
        var purge = ChkPurgeData.IsChecked == true;
        await System.Threading.Tasks.Task.Run(() => DoUninstall(purge));
        MessageBox.Show("知屿 已卸载完成。", "知屿");
        Close();
    }

    private void DoUninstall(bool purge)
    {
        // 结束主程序 + 等待退出
        try { foreach (var p in System.Diagnostics.Process.GetProcessesByName("知屿")) p.Kill(); } catch { }
        System.Threading.Thread.Sleep(800);
        // 删桌面快捷方式（用户桌面 + 公共桌面）
        foreach (var dir in new[]
        {
            Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonDesktopDirectory),
        })
        {
            try { var p = Path.Combine(dir, "知屿.lnk"); if (File.Exists(p)) File.Delete(p); } catch { }
        }
        // 删注册表卸载项 + 开机自启
        try { Registry.CurrentUser.DeleteSubKeyTree(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\知屿", false); } catch { }
        try { using var run = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run", true); run?.DeleteValue("知屿", false); } catch { }
        // 勾选则删本地个人数据（主题配置 + userData）
        if (purge)
        {
            try { Directory.Delete(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "zhiyu"), true); } catch { }
            try { Directory.Delete(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "知屿"), true); } catch { }
        }
        // 删安装目录（重试，避免进程占用删不掉）
        for (int i = 0; i < 6; i++)
        {
            try { Directory.Delete(_installRoot, true); break; }
            catch { System.Threading.Thread.Sleep(500); }
        }
    }
}
