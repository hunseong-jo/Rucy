# 마우스·키보드를 움직입니다. (윈도우 내장 .NET — 설치할 것 없음)
# 파이썬(computer.py)이 부릅니다:
#   powershell -ExecutionPolicy Bypass -File input.ps1 -Action click -X 640 -Y 360
#
# ⚠️ 이 파일은 **BOM 있는 UTF-8**로 저장해야 합니다(screen.ps1과 같은 이유 —
#    PowerShell 5.1은 BOM이 없으면 cp949로 읽어 한글 주석이 깨지며 파싱 오류가 납니다).
#
# 좌표는 **실제 화면 좌표**입니다(이미지 픽셀 → 화면 좌표 변환은 computer.py가 합니다).
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("move", "click", "doubleclick", "rightclick", "drag", "type", "keys", "scroll", "open", "title")]
    [string]$Action,
    [int]$X = -1,
    [int]$Y = -1,
    [int]$X2 = -1,
    [int]$Y2 = -1,
    [string]$Text = "",
    [int]$Amount = 0,
    [string]$Expect = ""      # type/keys 전용: 글자가 들어가야 할 창 제목 (다르면 안 넣고 실패)
)
$ErrorActionPreference = "Stop"
# ⚠️ 파워셸 5.1은 기본적으로 콘솔 코드페이지(cp949)로 내보냅니다. 파이썬은 utf-8로 읽으므로
#    한글 창 제목이 깨진 글자로 도착합니다("3D 알약게임 기획" → "? 3D ˾���"). 그 깨진 제목을
#    모델에게 보여주면 "지금 어느 창인지"를 못 읽고 엉뚱한 창에 타이핑합니다. 여기서 맞춥니다.
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms

# 마우스는 .NET에 없어서 Win32(user32)를 직접 부릅니다.
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class LucyInput {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, int data, UIntPtr extra);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int max);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);

    public static string Title(IntPtr h) {
        StringBuilder sb = new StringBuilder(300);
        GetWindowText(h, sb, 300);
        return sb.ToString();
    }

    // 창을 **확실히** 맨 앞으로 끌어옵니다.
    //
    // SetForegroundWindow만 부르면 윈도우가 거절합니다 — 배경 프로세스가 사용자 몰래 창을
    // 가로채는 걸 막는 보호장치입니다(실측: 메모장은 떴는데 앞으로 안 나옴). 하지만 우리는
    // **앞으로 못 나온 창에 타이핑하면 글이 엉뚱한 창으로 가므로** 반드시 성공시켜야 합니다.
    // 두 가지 통상적인 우회를 함께 씁니다:
    //   ① ALT를 살짝 눌렀다 뗍니다 — 윈도우는 이걸 '사용자 입력'으로 보고 포커스 전환을 허락합니다.
    //   ② 목표 창의 입력 스레드에 우리 스레드를 붙입니다(AttachThreadInput) — 같은 스레드로 취급돼
    //      포커스를 넘겨줄 수 있습니다.
    public static bool ForceForeground(IntPtr h) {
        if (h == IntPtr.Zero) return false;
        ShowWindow(h, 9);                                  // SW_RESTORE — 최소화돼 있으면 복구
        // ALT를 '살짝 눌렀다 떼기'로 포커스 전환 허가를 받는데, **단독 ALT는 메뉴바를 활성화**시킵니다
        // (실측: 메모장 메뉴가 armed 상태가 되고, 다음 붙여넣기 ^v의 V가 '보기(V)' 메뉴를 열어
        //  글자가 통째로 사라짐). ALT를 누른 사이에 아무 기능 없는 키(0xE8, 미지정 VK)를 끼워 누르면
        // 메뉴는 활성화되지 않으면서 '사용자 입력' 판정은 그대로 받습니다.
        keybd_event(0x12, 0, 0, UIntPtr.Zero);             // ALT 누름
        keybd_event(0xE8, 0, 0, UIntPtr.Zero);             //   기능 없는 키 누름
        keybd_event(0xE8, 0, 2, UIntPtr.Zero);             //   기능 없는 키 뗌
        keybd_event(0x12, 0, 2, UIntPtr.Zero);             // ALT 뗌
        uint me = GetCurrentThreadId();
        uint target = GetWindowThreadProcessId(h, IntPtr.Zero);
        if (me != target) AttachThreadInput(me, target, true);
        BringWindowToTop(h);
        bool ok = SetForegroundWindow(h);
        if (me != target) AttachThreadInput(me, target, false);
        return ok;
    }
}
"@

# ⚠️ screen.ps1과 **같은 좌표계**에 서기 위해 반드시 필요합니다(자세한 이유는 screen.ps1의 같은 줄).
# 한쪽만 DPI를 알면 배율 125% PC에서 클릭이 25%씩 어긋난 곳에 떨어집니다.
[void][LucyInput]::SetProcessDPIAware()
# mouse_event 깃발값 (Win32 상수)
$LEFTDOWN = 0x0002; $LEFTUP = 0x0004
$RIGHTDOWN = 0x0008; $RIGHTUP = 0x0010
$WHEEL = 0x0800

function Move-To([int]$x, [int]$y) {
    if ($x -lt 0 -or $y -lt 0) { throw "좌표가 없습니다 (X·Y 필요)" }
    [void][LucyInput]::SetCursorPos($x, $y)
    Start-Sleep -Milliseconds 80          # 커서가 옮겨진 걸 앱이 알아챌 틈
}

function Click-Once() {
    [LucyInput]::mouse_event($LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    [LucyInput]::mouse_event($LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
}

function Assert-Focus([string]$expect) {
    # 타이핑 **직전**의 마지막 안전핀입니다. 모델이 "이 창에 넣겠다"고 판단한 시점(front 확인)과
    # 여기서 실제로 키가 들어가는 시점 사이에는 모델 호출 몇 초 + 실행 틈이 있습니다.
    # 그 사이 알림 팝업이 뜨거나 사용자가 다른 곳을 클릭하면 포커스가 바뀌어 있고,
    # 그대로 넣으면 글자가 엉뚱한 창(채팅창이면 재앙)으로 갑니다. 여기서 대조하고 다르면 멈춥니다.
    if ($expect -eq "") { return }    # 판단 시점 제목을 못 얻었으면 대조할 기준이 없습니다
    $now = [LucyInput]::Title([LucyInput]::GetForegroundWindow()).Trim()
    $want = $expect.Trim()
    # 완전일치를 요구하면 정상 상황도 막힙니다 — 메모장은 수정되면 제목 앞에 '*'가 붙고,
    # 브라우저는 탭 이동으로 꼬리가 바뀝니다. 그래서 한쪽이 다른 쪽을 품으면 같은 창으로 봅니다.
    if ($now -eq "" -or (-not $now.ToLower().Contains($want.ToLower()) -and -not $want.ToLower().Contains($now.ToLower()))) {
        throw "입력 직전 창이 바뀌었습니다 — 예상 '$want' / 지금 '$now'. 엉뚱한 창에 들어갈 수 있어 넣지 않았습니다."
    }
}

switch ($Action) {
    "move" { Move-To $X $Y }
    "click" { Move-To $X $Y; Click-Once }
    "doubleclick" {
        Move-To $X $Y
        Click-Once; Start-Sleep -Milliseconds 60; Click-Once
    }
    "rightclick" {
        Move-To $X $Y
        [LucyInput]::mouse_event($RIGHTDOWN, 0, 0, 0, [UIntPtr]::Zero)
        [LucyInput]::mouse_event($RIGHTUP, 0, 0, 0, [UIntPtr]::Zero)
    }
    "drag" {
        # 끌어다 놓기. 누른 채 **잘게 나눠 이동**해야 합니다 — 한 번에 순간이동하면
        # 대부분의 앱이 드래그로 인식하지 못합니다(드래그 판정은 '눌린 채 움직인 궤적'을 봅니다).
        if ($X2 -lt 0 -or $Y2 -lt 0) { throw "도착점이 없습니다 (X2·Y2 필요)" }
        Move-To $X $Y
        [LucyInput]::mouse_event($LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 150     # 누름을 앱이 알아챌 틈 (바로 움직이면 클릭으로 오인)
        $steps = 20
        for ($i = 1; $i -le $steps; $i++) {
            $px = [int]($X + ($X2 - $X) * $i / $steps)
            $py = [int]($Y + ($Y2 - $Y) * $i / $steps)
            [void][LucyInput]::SetCursorPos($px, $py)
            Start-Sleep -Milliseconds 15
        }
        Start-Sleep -Milliseconds 150     # 놓기 전 잠깐 — 도착점 인식 틈
        [LucyInput]::mouse_event($LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
    }
    "type" {
        # 글자는 SendKeys가 아니라 **클립보드 + Ctrl+V**로 넣습니다.
        # SendKeys는 한글을 IME에 한 자씩 밀어 넣다 자모가 쪼개지거나 씹힙니다(한국어의 고질병).
        # 붙여넣기는 완성된 문자열이 통째로 들어가므로 안전합니다.
        # (사용자의 클립보드 내용이 바뀌는 부작용이 있습니다 — computer.py가 시작 전에 고지합니다)
        if ($Text -eq "") { throw "넣을 글이 없습니다 (Text 필요)" }
        Assert-Focus $Expect
        Set-Clipboard -Value $Text
        Start-Sleep -Milliseconds 120
        Assert-Focus $Expect      # 클립보드 준비 120ms 사이에 바뀌었을 수도 있습니다
        [Windows.Forms.SendKeys]::SendWait("^v")
    }
    "keys" {
        # 특수키·단축키. SendKeys 문법: {ENTER} {TAB} {ESC} {F5} ^c(Ctrl+C) %{F4}(Alt+F4) 등
        if ($Text -eq "") { throw "보낼 키가 없습니다 (Text 필요)" }
        Assert-Focus $Expect
        [Windows.Forms.SendKeys]::SendWait($Text)
    }
    "scroll" {
        # 양수=위로, 음수=아래로. 1이 휠 한 칸(120)입니다.
        if ($Amount -eq 0) { $Amount = -3 }
        [LucyInput]::mouse_event($WHEEL, 0, 0, $Amount * 120, [UIntPtr]::Zero)
    }
    "open" {
        # 프로그램 이름(notepad, calc)이나 웹 주소(https://...)를 엽니다.
        #
        # ⚠️ **띄우고 끝내면 안 됩니다.** 창이 뜨기 전에 다음 동작(타이핑)이 날아가면
        #    글자가 **직전에 열려 있던 엉뚱한 창**에 들어갑니다(실제로 겪음 — 메모장이 안 떴는데
        #    "OK"만 돌려주는 바람에 붙여넣기가 다른 창으로 갔습니다. 그게 채팅창이었으면 큰일).
        #    그래서 창이 실제로 뜰 때까지 기다리고, 맨 앞으로 끌어오고, **못 띄우면 실패로 알립니다.**
        if ($Text -eq "") { throw "열 대상이 없습니다 (Text 필요)" }

        $before = [LucyInput]::GetForegroundWindow()

        # ⚠️ Start-Process가 아니라 .NET Process.Start를 씁니다.
        #    Start-Process는 이 PC에서 "필요한 정보를 모두 찾을 수 없습니다"(InvalidOperationException)로
        #    거부합니다 — 프로필 없이(-NoProfile) 비대화형으로 부를 때 생기는 고질병입니다(실측).
        #    .NET 쪽은 같은 조건에서 멀쩡히 뜨고, 프로세스 객체를 바로 줘서 창 핸들도 얻기 쉽습니다.
        $proc = [System.Diagnostics.Process]::Start($Text)
        if ($null -eq $proc) { throw "'$Text'을(를) 실행하지 못했습니다." }

        # 웹 주소는 이미 떠 있는 브라우저가 받으므로 새 창을 기다릴 수 없습니다. 그때는 잠깐만 쉽니다.
        if ($Text -match "^https?://") {
            Start-Sleep -Milliseconds 2500
        }
        else {
            # 창이 생길 때까지 최대 10초. 창 없는 프로그램일 수도 있으니 없어도 죽이진 않습니다.
            for ($i = 0; $i -lt 40; $i++) {
                Start-Sleep -Milliseconds 250
                $proc.Refresh()
                if ($proc.HasExited) { throw "'$Text'이(가) 곧바로 종료됐습니다 — 창이 뜨지 않았습니다." }
                if ($proc.MainWindowHandle -ne [IntPtr]::Zero) { break }
            }
            if ($proc.MainWindowHandle -eq [IntPtr]::Zero) {
                throw "'$Text'의 창이 10초 안에 뜨지 않았습니다 — 다음 동작이 엉뚱한 창에 들어갈 수 있어 멈춥니다."
            }
            [void][LucyInput]::ForceForeground($proc.MainWindowHandle)
            Start-Sleep -Milliseconds 500
        }

        $now = [LucyInput]::GetForegroundWindow()
        if ($now -eq $before) {
            # 창이 떴는데도 맨 앞으로 못 왔습니다(윈도우가 포커스 뺏기를 막는 경우가 있습니다).
            # 조용히 넘어가면 타이핑이 옛 창으로 갑니다 → 실패로 알려 모델이 클릭해서 띄우게 합니다.
            throw "'$Text'을(를) 열었지만 맨 앞으로 가져오지 못했습니다 — 창을 직접 클릭해야 합니다."
        }
    }
    "title" {
        # 지금 키보드 입력이 **어느 창으로 갈지** 알려줍니다. 타이핑 전에 확인용으로 씁니다.
        Write-Output ("TITLE " + [LucyInput]::Title([LucyInput]::GetForegroundWindow()))
    }
}
Write-Output "OK $Action"
