<#
.SYNOPSIS
  Register (or remove) the Windows Scheduled Task that keeps the household
  deployment's WSL distribution and app alive independently of any interactive
  development shell (private-household-deployment ticket 06b), and starts it
  after a Windows boot with nobody signed in (ticket 06c).

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
    * Triggers   : three, built natively —
                     - AtStartup: starts the keeper when Windows boots, before
                       any interactive logon (ticket 06c). Paired with the S4U
                       principal below it needs nobody signed in. Omit with
                       -NoBootTrigger.
                     - AtLogOn for this user.
                     - a -Once trigger (at registration time) repeating every
                       -RepetitionMinutes forever: the recovery path after a
                       controlled `wsl --shutdown` while you stay logged in (the
                       task re-runs `wsl.exe`, WSL boots, the keeper brings the
                       supervisor and app back), and it starts the keeper
                       immediately on registration.
                   MultipleInstances = IgnoreNew, so a second trigger firing
                   while the keeper already runs is a no-op (the keeper's own
                   pidfile refuses a duplicate too). The script reads the task
                   back and warns if the repetition did not attach (it varies by
                   Windows / PowerShell version).
    * Restart    : if the action process exits non-zero (e.g. `wsl.exe` returns
                   after `wsl --shutdown`), Task Scheduler restarts it after one
                   minute, up to 999 times. A clean stop (SIGTERM to the keeper,
                   exit 0) is left stopped on purpose.
    * Unbounded  : ExecutionTimeLimit 0 — the keeper is meant to run forever.
    * Power      : starts and keeps running on battery, and is not stopped when
                   the machine leaves idle. Host sleep/hibernate still stops the
                   service (spec item 24); pass -ConfigurePower to also set the
                   AC standby/hibernate timeouts to 0, or apply the powercfg
                   commands from the runbook by hand.
    * Idempotent : re-running replaces the task of the same name (-Force), so
                   repeated setup never leaves a duplicate keeper.

  Running the private Tailscale ingress unattended (so the household's HTTPS
  origin also returns after a reboot) is the other half of ticket 06c: enable
  Tailscale's "run unattended" mode on Windows, and set RECIPE_DEPLOY_KEEPER_SERVE
  in deploy/deploy.env so the keeper re-asserts Serve itself. This script only
  configures Task Scheduler; the boot-before-login walk-through, lifetime
  controls, diagnostics, and host power settings are documented in README
  "Operating the server" runbooks 17-18.

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

.PARAMETER NoBootTrigger
  Omit the AtStartup trigger, leaving only AtLogOn + the repetition (the
  ticket 06b behaviour). Use this only if the deployment must not come up until
  the owner signs in.

.PARAMETER Bash
  The shell inside WSL. Default "bash".

.PARAMETER WslPath
  The Windows wsl launcher. Default "wsl.exe".

.PARAMETER LogonType
  "S4U" (default, no stored password) or "Password" (prompts once; use only if
  WSL will not start under S4U on your host).

.PARAMETER ConfigurePower
  Also run `powercfg /change standby-timeout-ac 0` and
  `hibernate-timeout-ac 0` so an idle host on AC power does not sleep and drop
  household members (spec items 7, 24). Off by default — it changes a
  machine-wide setting. Battery timeouts and a laptop's lid-close action are
  left to the owner.

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
  [switch] $NoBootTrigger,
  [switch] $ConfigurePower,
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

# Independent triggers, each built natively (no copying .Repetition between
# trigger objects — that assignment is inconsistent across PowerShell versions):
#   * AtStartup — starts the keeper when Windows boots, before any interactive
#     logon (ticket 06c). Dropped by -NoBootTrigger.
#   * AtLogOn for this user — starts the keeper when the owner signs in.
#   * -Once at registration time, repeating every $RepetitionMinutes forever —
#     the recovery path after a controlled `wsl --shutdown` while the owner
#     stays logged in, and it also starts the keeper immediately on register.
# MultipleInstances = IgnoreNew (below) makes any later trigger firing a no-op
# while the keeper is still running.
$triggers = @()
if (-not $NoBootTrigger) {
  $triggers += (New-ScheduledTaskTrigger -AtStartup)
}
$triggers += (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME")
$triggers += (New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $RepetitionMinutes) `
    -RepetitionDuration ([TimeSpan]::MaxValue))

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
  -Description "Keeps the recipe household deployment's WSL '$Distro' distribution and app alive independent of an interactive shell (ticket 06b), and starts it at boot before login (ticket 06c). Runs deploy/wsl-keeper.sh run via wsl.exe." `
  -Force | Out-Null

$whoTriggers = if ($NoBootTrigger) {
  "at logon of $env:USERDOMAIN\$env:USERNAME"
}
else {
  "at boot (before login) and at logon of $env:USERDOMAIN\$env:USERNAME"
}
Write-Host "registered scheduled task '$TaskName'"
Write-Host "  triggers : $whoTriggers, then every $RepetitionMinutes min"
Write-Host "  restart  : on non-zero exit, after 1 min, up to 999 times; no execution time limit"
Write-Host "  logon    : $LogonType"
Write-Host "  command  : $WslPath $wslArgs"

# Read the task back and confirm the repetition actually attached — the
# recovery-after-`wsl --shutdown` path depends on it, and Task Scheduler
# behaviour here varies by Windows / PowerShell version (spec item 6: inspect
# the host before trusting exact settings).
$registered = Get-ScheduledTask -TaskName $TaskName
$repInterval = ($registered.Triggers |
  ForEach-Object { $_.Repetition.Interval } |
  Where-Object { $_ } | Select-Object -First 1)
if ($repInterval) {
  Write-Host "  verified : repetition interval $repInterval is in force"
}
else {
  Write-Warning ("no repetition interval attached to '$TaskName' on this host. " +
    'Recovery after "wsl --shutdown" will then wait for the next logon or the ' +
    '1-minute restart-on-failure only. Add a repeating trigger by hand in Task ' +
    'Scheduler, or see runbook 17.')
}

if (-not $NoBootTrigger) {
  $hasBoot = [bool]($registered.Triggers |
    Where-Object { $_.CimClass.CimClassName -eq 'MSFT_TaskBootTrigger' })
  if ($hasBoot) {
    Write-Host "  verified : at-boot trigger is in force (starts before interactive login)"
  }
  else {
    Write-Warning ("no at-boot trigger attached to '$TaskName' on this host. " +
      'The deployment will not come back until the owner signs in. Add an ' +
      '"At startup" trigger by hand in Task Scheduler, or see runbook 18.')
  }
}

if ($ConfigurePower) {
  Write-Host ""
  Write-Host "configuring host power (AC): no standby, no hibernate"
  powercfg /change standby-timeout-ac 0
  powercfg /change hibernate-timeout-ac 0
  Write-Host "  (battery timeouts left as-is; a laptop still needs lid-close = Do nothing)"
}
else {
  Write-Host ""
  Write-Host "Pair with host power settings so the machine does not sleep while it"
  Write-Host "should be serving (runbook 17) — re-run with -ConfigurePower, or by hand on AC:"
  Write-Host "  powercfg /change standby-timeout-ac 0"
  Write-Host "  powercfg /change hibernate-timeout-ac 0"
}

Write-Host ""
Write-Host "start it now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "check it:      wsl.exe -d $Distro -- $Bash '$scriptPath' status"
Write-Host ""
if (-not $NoBootTrigger) {
  Write-Host "Boot-before-login (ticket 06c): also make the private HTTPS ingress unattended —"
  Write-Host "  1. enable Tailscale 'run unattended' on Windows (tray > Preferences), and"
  Write-Host "  2. set RECIPE_DEPLOY_KEEPER_SERVE=1 in deploy/deploy.env so the keeper"
  Write-Host "     re-asserts Serve after a reboot with nobody logged in."
  Write-Host "Then reboot and verify from a permitted client before signing in (runbook 18)."
  Write-Host ""
}
Get-ScheduledTaskInfo -TaskName $TaskName |
  Format-List TaskName, LastRunTime, LastTaskResult, NextRunTime
