<#
.SYNOPSIS
  Register (or remove) the Windows Scheduled Task that keeps the household
  deployment's WSL distribution and app alive independently of any interactive
  development shell — private-household-deployment ticket 06b.

.DESCRIPTION
  The task runs one long-lived foreground command:

      wsl.exe -d <Distro> -- <Bash> <Checkout>/deploy/wsl-keeper.sh run

  While that command runs the WSL distribution stays up (a distro stops when its
  last process exits — a systemd service *inside* WSL cannot hold it open), and
  deploy/wsl-keeper.sh keeps exactly one deploy/supervise.sh (ticket 06a), and
  so the app, running above it. Closing the IDE and every terminal changes
  nothing: the keeper belongs to Task Scheduler, not to a shell.

  Task settings:
    * Principal  : the invoking user, LogonType S4U (no interactive logon, no
                   stored password). If WSL refuses to start under S4U on your
                   host, re-run with -LogonType Password (prompts once).
    * Triggers   : AtLogOn for this user, plus a 5-minute repetition that runs
                   indefinitely. The repetition is the recovery path after a
                   controlled `wsl --shutdown` while you stay logged in — within
                   five minutes the task re-runs `wsl.exe`, WSL boots, and the
                   keeper brings the supervisor and app back. MultipleInstances
                   = IgnoreNew, so a repetition tick is a no-op while the keeper
                   is still running.
    * Restart    : if the action process exits non-zero (e.g. `wsl.exe` returns
                   after `wsl --shutdown`), Task Scheduler restarts it after one
                   minute, up to 999 times. A clean stop (SIGTERM to the keeper,
                   exit 0) is left stopped on purpose.
    * Unbounded  : ExecutionTimeLimit 0 — the keeper is meant to run forever.
    * Power      : starts and keeps running on battery, and is not stopped when
                   the machine leaves idle. Host sleep/hibernate still stops the
                   service (spec item 24) — see the runbook for the powercfg
                   settings to pair with this task.
    * Idempotent : re-running replaces the task of the same name (-Force), so
                   repeated setup never leaves a duplicate keeper.

  Starting this before an interactive Windows login (a full reboot) and running
  Tailscale ingress unattended are ticket 06c, which adds an AtStartup trigger
  onto this same task. This script only configures Task Scheduler; lifetime
  controls, diagnostics, and host power settings are documented in README
  "Operating the server" runbook 17.

.PARAMETER Distro
  The WSL distribution the deployment runs in (wsl.exe -d value). Match
  RECIPE_DEPLOY_WSL_DISTRO in deploy/deploy.env.

.PARAMETER Checkout
  Absolute path to the repository checkout *inside WSL* (e.g. /home/you/recipe).
  Match RECIPE_DEPLOY_CHECKOUT. Use a path without spaces.

.PARAMETER TaskName
  Scheduled Task name. Default "RecipeAppWslKeeper".

.PARAMETER RepetitionMinutes
  Minutes between repetition ticks (the post-`wsl --shutdown` recovery path).
  Default 5.

.PARAMETER Bash
  The shell inside WSL. Default "bash".

.PARAMETER WslPath
  The Windows wsl launcher. Default "wsl.exe".

.PARAMETER LogonType
  "S4U" (default, no stored password) or "Password" (prompts once; use only if
  WSL will not start under S4U on your host).

.PARAMETER Unregister
  Remove the task instead of creating it.

.PARAMETER ShowCommand
  Print the resolved wsl.exe invocation and exit without touching Task
  Scheduler. Handy for a one-off manual run:
      wsl.exe -d <Distro> -- bash <Checkout>/deploy/wsl-keeper.sh run

.EXAMPLE
  .\deploy\windows\register-keeper-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe

.EXAMPLE
  .\deploy\windows\register-keeper-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe -Unregister
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string] $Distro,
  [Parameter(Mandatory = $true)] [string] $Checkout,
  [string] $TaskName = "RecipeAppWslKeeper",
  [int] $RepetitionMinutes = 5,
  [string] $Bash = "bash",
  [string] $WslPath = "wsl.exe",
  [ValidateSet("S4U", "Password")] [string] $LogonType = "S4U",
  [switch] $Unregister,
  [switch] $ShowCommand
)

$ErrorActionPreference = "Stop"

# wsl-keeper.sh sources deploy/lib.sh by its own path, so the working directory
# does not matter; pass an absolute script path, single-quoted for the WSL-side
# shell so a space in $Checkout does not split it.
$scriptPath = "$Checkout/deploy/wsl-keeper.sh"
$wslArgs = "-d $Distro -- $Bash '$scriptPath' run"

if ($ShowCommand) {
  Write-Host "$WslPath $wslArgs"
  return
}

if ($Unregister) {
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "removed scheduled task '$TaskName'"
  }
  else {
    Write-Host "no scheduled task '$TaskName' to remove"
  }
  return
}

$action = New-ScheduledTaskAction -Execute $WslPath -Argument $wslArgs

# AtLogOn for this user, plus an indefinite repetition as the post-shutdown
# recovery path. Building the repetition on a logon trigger is not exposed
# directly by New-ScheduledTaskTrigger, so borrow it from a throwaway -Once
# trigger (a documented idiom).
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$repeating = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes $RepetitionMinutes) `
  -RepetitionDuration ([TimeSpan]::MaxValue)
$logon.Repetition = $repeating.Repetition
$triggers = @($logon)

# ExecutionTimeLimit 0 = run indefinitely. Restart the action if it exits
# non-zero (e.g. wsl.exe returning after `wsl --shutdown`); a clean keeper stop
# exits 0 and is left stopped. Keep running on battery and past idle end; host
# sleep is a separate powercfg concern (runbook 17).
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -DontStopOnIdleEnd `
  -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -RestartCount 999 `
  -MultipleInstances IgnoreNew

$principalArgs = @{
  UserId   = "$env:USERDOMAIN\$env:USERNAME"
  RunLevel = "Limited"
}
if ($LogonType -eq "Password") {
  $principalArgs["LogonType"] = "Password"
  Write-Host "You will be prompted for the account password (stored by Task Scheduler)."
}
else {
  $principalArgs["LogonType"] = "S4U"
}
$principal = New-ScheduledTaskPrincipal @principalArgs

Register-ScheduledTask -TaskName $TaskName `
  -Action $action -Trigger $triggers -Settings $settings -Principal $principal `
  -Description "Keeps the recipe household deployment's WSL '$Distro' distribution and app alive independent of an interactive shell (ticket 06b). Runs deploy/wsl-keeper.sh run via wsl.exe." `
  -Force | Out-Null

Write-Host "registered scheduled task '$TaskName'"
Write-Host "  triggers : at logon of $env:USERDOMAIN\$env:USERNAME, then every $RepetitionMinutes min"
Write-Host "  restart  : on non-zero exit, after 1 min, up to 999 times; no execution time limit"
Write-Host "  logon    : $LogonType"
Write-Host "  command  : $WslPath $wslArgs"
Write-Host ""
Write-Host "start it now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "check it:      wsl.exe -d $Distro -- $Bash '$scriptPath' status"
Write-Host ""
Write-Host "Pair with host power settings so the machine does not sleep while it"
Write-Host "should be serving (runbook 17), e.g. on AC:"
Write-Host "  powercfg /change standby-timeout-ac 0"
Write-Host "  powercfg /change hibernate-timeout-ac 0"
Write-Host ""
Write-Host "Boot-before-login start and unattended Tailscale ingress are ticket 06c."
Write-Host ""
Get-ScheduledTaskInfo -TaskName $TaskName |
  Format-List TaskName, LastRunTime, LastTaskResult, NextRunTime
