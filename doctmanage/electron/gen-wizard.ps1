Add-Type -AssemblyName System.Drawing
# 生成 Inno Setup 安装窗口品牌图（BMP）
$dir = "C:\Users\50534\Desktop\桌面整理\文件夹归档\项目代码\document\documentplatform\doctmanage\electron"

function New-GradientBmp($w, $h, $title, $sub) {
  $bmp = New-Object System.Drawing.Bitmap($w, $h)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  # 深蓝渐变
  $rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
  $c1 = [System.Drawing.Color]::FromArgb(9, 15, 33)
  $c2 = [System.Drawing.Color]::FromArgb(37, 74, 160)
  $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect, $c1, $c2, 90)
  $g.FillRectangle($brush, $rect)
  # 顶部光晕
  $halo = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(36, 90, 210))
  $g.FillEllipse($halo, -40, -50, $w + 80, 160)
  $halo.Dispose()
  # 主标题
  $fontMain = New-Object System.Drawing.Font('Microsoft YaHei', [math]::Floor($h / 10), [System.Drawing.FontStyle]::Bold)
  $fontSub = New-Object System.Drawing.Font('Microsoft YaHei', [math]::Max(8, [math]::Floor($h / 28)))
  $white = [System.Drawing.Brushes]::White
  $g.DrawString($title, $fontMain, $white, 16, [math]::Floor($h * 0.36))
  $g.DrawString($sub, $fontSub, $white, 17, [math]::Floor($h * 0.36) + [math]::Floor($h / 10) + 6)
  # 底部版本
  $fontVer = New-Object System.Drawing.Font('Microsoft YaHei', [math]::Max(7, [math]::Floor($h / 36)))
  $dim = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(190, 210, 255))
  $g.DrawString('v1.8.0  ·  zhiyur.cn', $fontVer, $dim, 16, $h - 28)
  $fontMain.Dispose(); $fontSub.Dispose(); $fontVer.Dispose(); $dim.Dispose(); $brush.Dispose()
  $g.Dispose()
  return $bmp
}

# 左侧大横幅 164x314
$b1 = New-GradientBmp 164 314 '知屿' '让知识成为岛屿'
$b1.Save("$dir\wizard-image.bmp", [System.Drawing.Imaging.ImageFormat]::Bmp)
$b1.Dispose()
# 左上小图 55x55
$b2 = New-GradientBmp 55 55 '知' ''
$b2.Save("$dir\wizard-small.bmp", [System.Drawing.Imaging.ImageFormat]::Bmp)
$b2.Dispose()
Write-Output "BMP 已生成:"
Get-Item "$dir\wizard-image.bmp", "$dir\wizard-small.bmp" | Select-Object Name, Length
