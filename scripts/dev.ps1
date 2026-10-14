# Edge Claw development helper.
#
#   .\scripts\dev.ps1 reload          reinstall the plugin from this folder and relaunch the pet
#   .\scripts\dev.ps1 launch          start the pet (outside Claude's job, see CLAUDE.md)
#   .\scripts\dev.ps1 quit            send the pet home
#   .\scripts\dev.ps1 play Confetti   play one animation now (any name in pet/clawd_sprites.json)
#   .\scripts\dev.ps1 doze            make it nod off now
#   .\scripts\dev.ps1 pose Thinking   hold a pose for 20 s: Laptop | Thinking | Desktop | Lightbulb
#   .\scripts\dev.ps1 state done      pretend Claude reported a status: working | done | interrupted | idle
#   .\scripts\dev.ps1 state working permission   ...with an attention: permission | question
#   .\scripts\dev.ps1 test            validate the plugin and run its tests
#
# reload picks up pet changes at once; hook (register.tsx) changes load in a new Claude session.
# Bump "version" in .claude-plugin/plugin.json before reload, or the cached copy is not replaced.

param([Parameter(Position = 0)][string]$Action = 'help', [Parameter(Position = 1)][string]$Arg1, [Parameter(Position = 2)][string]$Arg2)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Data = Join-Path $HOME '.claude\edge-claw'
$StateFile = Join-Path $Data 'state.json'
$Plugin = 'edge-claw@edge-claw-local'

# The Claude Code that ships with the desktop app (the one on PATH may be older than mods need).
function Get-ClaudeCode {
    $exe = Get-ChildItem (Join-Path $env:APPDATA 'Claude\claude-code') -Recurse -Filter claude.exe -ErrorAction SilentlyContinue |
        Sort-Object { [version](($_.FullName -split '\\claude-code\\')[1].Split('\')[0]) } | Select-Object -Last 1
    if (-not $exe) { throw 'No Claude Code found under %APPDATA%\Claude\claude-code' }
    $exe.FullName
}

function Get-InstalledPet {
    $dir = Get-ChildItem (Join-Path $HOME '.claude\plugins\cache\edge-claw-local\edge-claw') -Directory |
        Sort-Object { [version]$_.Name } | Select-Object -Last 1
    Join-Path $dir.FullName 'pet\clawd.pyw'
}

function Get-Pythonw {
    $dirs = Get-ChildItem (Join-Path $env:LOCALAPPDATA 'Programs\Python') -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending
    foreach ($d in $dirs) { $p = Join-Path $d.FullName 'pythonw.exe'; if (Test-Path $p) { return $p } }
    if (Test-Path 'C:\Windows\pyw.exe') { return 'C:\Windows\pyw.exe' }
    'pythonw'
}

function Send-State([hashtable]$fields) {
    New-Item -ItemType Directory -Force $Data | Out-Null
    $fields.ts = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
    if ($fields.cmd) { $fields.cmdId = $fields.ts }
    [IO.File]::WriteAllText($StateFile, ($fields | ConvertTo-Json -Compress))
}

function Stop-Pet { Send-State @{ status = 'idle'; attention = $null; cmd = 'quit' }; Start-Sleep -Seconds 2 }

function Start-Pet {
    $cmd = "`"$(Get-Pythonw)`" `"$(Get-InstalledPet)`""
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    if ($r.ReturnValue -ne 0) { throw "Win32_Process.Create returned $($r.ReturnValue)" }
    "pet started (pid $($r.ProcessId))"
}

switch ($Action) {
    'reload' {
        $cc = Get-ClaudeCode
        & $cc plugin validate $Root
        & $cc plugin marketplace update edge-claw-local
        & $cc plugin update $Plugin
        Stop-Pet; Start-Pet
    }
    'launch' { Start-Pet }
    'quit' { Stop-Pet; 'pet sent home' }
    'play' { Send-State @{ status = 'idle'; attention = $null; cmd = 'play'; anim = $Arg1 } }
    'doze' { Send-State @{ status = 'idle'; attention = $null; cmd = 'doze' } }
    'pose' { Send-State @{ status = 'idle'; attention = $null; cmd = 'pose'; anim = $Arg1 } }
    'state' { Send-State @{ status = $Arg1; attention = $(if ($Arg2) { $Arg2 } else { $null }) } }
    'test' { $cc = Get-ClaudeCode; & $cc plugin validate $Root; & $cc plugin test $Root }
    default { Get-Content $PSCommandPath | Where-Object { $_ -like '#*' } | Select-Object -First 16 }
}
