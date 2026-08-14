using System;
using System.IO;
using System.Windows;

namespace ZhiyuInstaller;

public static class Program
{
    [STAThread]
    public static void Main()
    {
        // 在 WPF 框架初始化前提取嵌入的原生 dll（vcruntime140 等加载时机极早，必须在这里提取）
        ExtractNativeDlls();
        var app = new App();
        app.InitializeComponent();
        app.Run(new MainWindow());
    }

    static void ExtractNativeDlls()
    {
        var dir = AppContext.BaseDirectory;
        var asm = typeof(Program).Assembly;
        foreach (var res in asm.GetManifestResourceNames())
        {
            if (!res.EndsWith(".dll", StringComparison.OrdinalIgnoreCase)) continue;
            var marker = ".native.";
            var idx = res.IndexOf(marker, StringComparison.Ordinal);
            if (idx < 0) continue;
            var dllName = res.Substring(idx + marker.Length);
            var path = Path.Combine(dir, dllName);
            if (File.Exists(path)) continue;
            try
            {
                using var s = asm.GetManifestResourceStream(res);
                if (s == null) continue;
                using var f = File.Create(path);
                s.CopyTo(f);
            }
            catch { /* 忽略，尝试从系统加载 */ }
        }
    }
}
