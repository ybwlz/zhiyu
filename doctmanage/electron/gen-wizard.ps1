Add-Type -AssemblyName System.Drawing
# 生成 Inno Setup 安装窗口品牌图（强制 24bit BMP，保存后验证位深）
$dir = "C:\Users\50534\Desktop\桌面整理\文件夹归档\项目代码\document\documentplatform\doctmanage\electron"

function New-GradientBmp($w, $h, $title, $sub) {
  # Inno Setup 要求 24bit BMP，用 Format24bppRgb 创建并保存
  $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
  $c1 = [System.Drawing.Color]::FromArgb(9, 15, 33)
  $c2 = [System.Drawing.Color]::FromArgb(37, 74, 160)
  $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect, $c1, $c2, 90)
  $g.FillRectangle($brush, $rect)
  $halo = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(36, 90, 210))
  $g.FillEllipse($halo, -40, -50, $w + 80, 160)
  $halo.Dispose()
  $fontMain = New-Object System.Drawing.Font('Microsoft YaHei', [math]::Floor($h / 10), [System.Drawing.FontStyle]::Bold)
  $fontSub = New-Object System.Drawing.Font('Microsoft YaHei', [math]::Max(8, [math]::Floor($h / 28)))
  $white = [System.Drawing.Brushes]::White
  $g.DrawString($title, $fontMain, $white, 16, [math]::Floor($h * 0.36))
  $g.DrawString($sub, $fontSub, $white, 17, [math]::Floor($h * 0.36) + [math]::Floor($h / 10) + 6)
  $fontVer = New-Object System.Drawing.Font('Microsoft YaHei', [math]::Max(7, [math]::Floor($h / 36)))
  $dim = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(190, 210, 255))
  $g.DrawString('v1.8.0  ·  zhiyur.cn', $fontVer, $dim, 16, $h - 28)
  $fontMain.Dispose(); $fontSub.Dispose(); $fontVer.Dispose(); $dim.Dispose(); $brush.Dispose()
  $g.Dispose()
  return $bmp
}

$b1 = New-GradientBmp 164 314 '知屿' '让知识成为岛屿'
$b1.Save("$dir\wizard-image.bmp", [System.Drawing.Imaging.ImageFormat]::Bmp)
$b2 = New-GradientBmp 55 55 '知' ''
$b2.Save("$dir\wizard-small.bmp", [System.Drawing.Imaging.ImageFormat]::Bmp)
# 读回验证位深（必须 24bppRgb，Inno 才认）
$c1 = [System.Drawing.Bitmap]::FromFile("$dir\wizard-image.bmp")
$c2 = [System.Drawing.Bitmap]::FromFile("$dir\wizard-small.bmp")
Write-Output ("大图: {0}x{1} {2}" -f $c1.Width, $c1.Height, $c1.PixelFormat)
Write-Output ("小图: {0}x{1} {2}" -f $c2.Width, $c2.Height, $c2.PixelFormat)
$c1.Dispose(); $c2.Dispose(); $b1.Dispose(); $b2.Dispose()
