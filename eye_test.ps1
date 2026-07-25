# 눈(비전) 시험용 그림을 만듭니다 — 큰 네 자리 숫자 한 개.
# 왜 숫자인가: 모델이 그림을 못 봐도 "고양이 사진이네요" 식으로 둘러대면 채점이 안 됩니다.
# 매번 새로 뽑은 네 자리 숫자는 **보지 않고는 맞힐 수 없습니다**(1/9000).
#
# ⚠️ BOM 있는 UTF-8로 저장할 것 (PowerShell 5.1은 BOM이 없으면 한글 주석을 cp949로 읽어 파싱이 깨집니다)
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [Parameter(Mandatory = $true)][string]$Code
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$img = New-Object Drawing.Bitmap 640, 360
$g = [Drawing.Graphics]::FromImage($img)
$g.Clear([Drawing.Color]::White)
$g.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAlias

$font = New-Object Drawing.Font "Arial", 120, ([Drawing.FontStyle]::Bold)
$brush = New-Object Drawing.SolidBrush ([Drawing.Color]::Black)
$fmt = New-Object Drawing.StringFormat
$fmt.Alignment = [Drawing.StringAlignment]::Center
$fmt.LineAlignment = [Drawing.StringAlignment]::Center
$g.DrawString($Code, $font, $brush, (New-Object Drawing.RectangleF 0, 0, 640, 360), $fmt)

$g.Dispose()
$img.Save($Out, [Drawing.Imaging.ImageFormat]::Png)
$img.Dispose()
Write-Output "ok"
