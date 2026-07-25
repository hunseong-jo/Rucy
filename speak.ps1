param(
    # 이름을 File로 두면 powershell.exe 자신의 -File 인자와 헷갈립니다. TextFile로 구분합니다.
    [Parameter(Mandatory = $true)][string]$TextFile,
    [string]$Voice = "",
    [int]$Rate = 0,
    [int]$Volume = 100
)
# 루시의 목소리. 윈도우 내장 음성(SAPI)이라 설치할 것이 없습니다.
# 파이썬이 이 스크립트를 별도 프로세스로 띄우고, 멈출 때는 프로세스를 죽입니다.
# (말하는 중에도 프로세스를 죽이면 소리가 즉시 끊깁니다 — 사용자가 엔터를 치면 그렇게 합니다)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech

$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($Voice) {
    try { $s.SelectVoice($Voice) }
    catch { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet,
                                  [System.Speech.Synthesis.VoiceAge]::NotSet, 0,
                                  [System.Globalization.CultureInfo]::GetCultureInfo('ko-KR')) }
}
$s.Rate = $Rate
$s.Volume = $Volume

# 파이썬이 UTF-8로 써 둔 파일을 읽습니다(명령줄로 넘기면 한글이 깨집니다).
$text = [System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8)
if ($text.Trim()) { $s.Speak($text) }
$s.Dispose()
