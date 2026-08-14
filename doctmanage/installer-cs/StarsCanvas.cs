using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace ZhiyuInstaller;

/// <summary>用 DrawingContext 精确绘制星空软点（复刻 Electron 的 radial-gradient 1px 光点）。</summary>
public class StarsCanvas : Canvas
{
    protected override void OnRender(DrawingContext dc)
    {
        base.OnRender(dc);

        // (left%, top%, 半径px, alpha)
        var stars = new (double, double, double, byte)[]
        {
            (0.18, 0.28, 1.0, 179), (0.72, 0.18, 1.0, 140), (0.42, 0.62, 1.5, 102),
            (0.86, 0.70, 1.0, 140), (0.08, 0.82, 1.0, 89),  (0.56, 0.86, 1.5, 102),
            (0.92, 0.42, 1.0, 128), (0.30, 0.10, 1.0, 115), (0.64, 0.48, 1.0, 77),
            (0.12, 0.55, 1.0, 102),
        };

        foreach (var (lx, ty, r, a) in stars)
        {
            var brush = new SolidColorBrush(Color.FromArgb(a, 255, 255, 255));
            var center = new Point(lx * ActualWidth, ty * ActualHeight);
            dc.DrawEllipse(brush, null, center, r, r);
        }
    }
}
