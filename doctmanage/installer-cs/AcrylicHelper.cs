using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;

namespace ZhiyuInstaller;

internal enum AccentState
{
    ACCENT_DISABLED = 0,
    ACCENT_ENABLE_GRADIENT = 1,
    ACCENT_ENABLE_TRANSPARENTGRADIENT = 2,
    ACCENT_ENABLE_BLURBEHIND = 3,
    ACCENT_ENABLE_ACRYLICBLURBEHIND = 4,
}

[StructLayout(LayoutKind.Sequential)]
internal struct AccentPolicy
{
    public AccentState AccentState;
    public int AccentFlags;
    public int GradientColor;
    public int AnimationId;
}

[StructLayout(LayoutKind.Sequential)]
internal struct WindowCompositionAttributeData
{
    public int Attribute;
    public IntPtr Data;
    public int SizeOfData;
}

[StructLayout(LayoutKind.Sequential)]
internal struct MARGINS
{
    public int leftWidth;
    public int rightWidth;
    public int topHeight;
    public int bottomHeight;
}

internal static class AcrylicHelper
{
    [DllImport("user32.dll")]
    private static extern int SetWindowCompositionAttribute(IntPtr hwnd, ref WindowCompositionAttributeData data);

    [DllImport("dwmapi.dll")]
    private static extern int DwmExtendFrameIntoClientArea(IntPtr hwnd, ref MARGINS margins);

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int attrValue, int attrSize);

    private const int WCA_ACCENT_POLICY = 19;
    private const int DWMWA_WINDOW_CORNER_PREFERENCE = 33;
    private const int DWMWCP_ROUND = 2;

    /// <summary>
    /// WPF Acrylic 毛玻璃正确实现：
    /// 1. DwmExtendFrameIntoClientArea 把 DWM 材质扩展到整个客户区（关键，否则黑底）
    /// 2. CompositionTarget.BackgroundColor 透明
    /// 3. SetWindowCompositionAttribute 启用 Acrylic + tint 色
    /// 4. 系统圆角
    /// </summary>
    public static void Enable(Window window, byte alpha = 150, byte r = 11, byte g = 18, byte b = 38)
    {
        var hwnd = new WindowInteropHelper(window).Handle;
        if (hwnd == IntPtr.Zero) return;

        // 1. 关键：把 DWM frame 扩展到整个客户区，让 Acrylic 材质能覆盖窗口
        var margins = new MARGINS { leftWidth = -1, rightWidth = -1, topHeight = -1, bottomHeight = -1 };
        DwmExtendFrameIntoClientArea(hwnd, ref margins);

        // 2. 让 WPF 窗口背景真正透明
        var source = HwndSource.FromHwnd(hwnd);
        if (source?.CompositionTarget != null)
            source.CompositionTarget.BackgroundColor = Colors.Transparent;

        // 3. Acrylic 材质 + 深蓝 tint（GradientColor 为 ABGR）
        int gradientColor = (alpha << 24) | (b << 16) | (g << 8) | r;
        var accent = new AccentPolicy
        {
            AccentState = AccentState.ACCENT_ENABLE_ACRYLICBLURBEHIND,
            AccentFlags = 2,
            GradientColor = gradientColor,
            AnimationId = 0,
        };
        var accentPtr = Marshal.AllocHGlobal(Marshal.SizeOf(accent));
        try
        {
            Marshal.StructureToPtr(accent, accentPtr, false);
            var data = new WindowCompositionAttributeData
            {
                Attribute = WCA_ACCENT_POLICY,
                Data = accentPtr,
                SizeOfData = Marshal.SizeOf(accent),
            };
            SetWindowCompositionAttribute(hwnd, ref data);
        }
        finally
        {
            Marshal.FreeHGlobal(accentPtr);
        }

        // 4. 系统圆角
        int corner = DWMWCP_ROUND;
        DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ref corner, sizeof(int));
    }
}
