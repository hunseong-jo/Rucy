# 화면을 찍어 PNG로 저장합니다. (윈도우 내장 .NET — 설치할 것 없음)
# 파이썬(screen.py)이 부릅니다:
#   powershell -ExecutionPolicy Bypass -File screen.ps1 -Out C:\...\shot.png -Mode screen -MaxWidth 1920
#
# ⚠️ 이 파일은 **BOM 있는 UTF-8**로 저장해야 합니다. PowerShell 5.1은 BOM이 없으면 cp949로 읽어서
#    한글 주석이 깨진 문자가 되고 "MissingEndParenthesis" 같은 엉뚱한 파싱 오류가 납니다(실제로 겪음).
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [ValidateSet("screen", "all", "active")][string]$Mode = "screen",
    [int]$MaxWidth = 1920
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

# 맨 앞 창이 어디에 있는지 알아내려면 Win32를 불러야 합니다(.NET에는 없습니다).
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class LucyWin {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

# ⚠️ 반드시 화면을 만지기 **전에** 불러야 합니다.
# 이걸 빼면 윈도우가 이 프로세스를 속입니다 — 화면 배율이 125%인 PC에서 실제 1766x1036인 화면을
# 1413x829라고 알려주고, 캡처도 그 크기로 **줄여서** 줍니다(글자가 뭉개져 오류 메시지를 못 읽습니다).
# 게다가 input.ps1과 좌표계가 어긋나면 클릭이 엉뚱한 곳에 떨어집니다.
# 그래서 화면을 보는 쪽(screen.ps1)과 만지는 쪽(input.ps1) **둘 다** 이 줄이 있어야 합니다.
[void][LucyWin]::SetProcessDPIAware()

$front = [LucyWin]::GetForegroundWindow()

switch ($Mode) {
    "active" {
        # 맨 앞 창 하나만.
        $r = New-Object LucyWin+RECT
        [void][LucyWin]::GetWindowRect($front, [ref]$r)
        $bounds = New-Object Drawing.Rectangle $r.Left, $r.Top, ($r.Right - $r.Left), ($r.Bottom - $r.Top)
    }
    "all" {
        # 모니터 전부(가상 화면). 듀얼이면 가로가 두 배가 되므로 글자가 작아집니다.
        $bounds = [Windows.Forms.SystemInformation]::VirtualScreen
    }
    default {
        # 기본: 맨 앞 창이 놓인 **모니터 한 대**.
        # 가상 화면 전체를 찍으면 3840px가 1920으로 줄면서 모니터당 960px가 되어
        # 오류 메시지 글자가 뭉개집니다. 보통은 보여주려는 창이 있는 모니터만 있으면 됩니다.
        $bounds = [Windows.Forms.Screen]::FromHandle($front).Bounds
    }
}
if ($bounds.Width -le 0 -or $bounds.Height -le 0) { throw "화면 크기를 읽지 못했습니다." }

$shot = New-Object Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [Drawing.Graphics]::FromImage($shot)
$g.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $shot.Size)
$g.Dispose()

# 너무 크면 base64가 부풀어 무료 모델의 토큰 한도를 태웁니다. 긴 변 기준으로 줄이되,
# 글자가 뭉개지면 오류를 못 읽으므로 고품질 보간을 씁니다.
if ($MaxWidth -gt 0 -and $shot.Width -gt $MaxWidth) {
    $h = [int]($shot.Height * $MaxWidth / $shot.Width)
    $small = New-Object Drawing.Bitmap $MaxWidth, $h
    $g2 = [Drawing.Graphics]::FromImage($small)
    $g2.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g2.DrawImage($shot, 0, 0, $MaxWidth, $h)
    $g2.Dispose()
    $shot.Dispose()
    $shot = $small
}

$shot.Save($Out, [Drawing.Imaging.ImageFormat]::Png)
$w = $shot.Width; $h = $shot.Height
$shot.Dispose()
# BOUNDS = 찍힌 영역의 실제 화면 좌표(왼쪽 위 오프셋 + 원본 크기). 컴퓨터 조작(computer.py)이
# 이미지 픽셀 좌표를 실제 클릭 좌표로 되돌릴 때 씁니다(듀얼 모니터 오프셋 + 축소 배율 보정).
# ⚠️ 크기("w x h")를 마지막 줄에 둬야 합니다 — screen.py가 마지막 줄을 화면에 보여줍니다.
Write-Output "BOUNDS $($bounds.Left) $($bounds.Top) $($bounds.Width) $($bounds.Height)"
Write-Output "$w x $h"
