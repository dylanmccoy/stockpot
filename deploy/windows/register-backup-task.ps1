<#
.SYNOPSIS
  Register (or remove) the Windows Scheduled Task that runs the household
  deployment's daily SQLite backup unattended — private-household-deployment
  ticket 07a.

.DESCRIPTION
  The task runs, once a day, whether or not a user is signed in:

      wsl.exe -d <Distro> -- <Bash> <Checkout>/deploy/backup-run.sh

  deploy/backup-run.sh takes ONE live online-backup snapshot of the configured
  deployment database into RECIPE_DEPLOY_BACKUP_DIR and appends a result line to
  the backup run log. It uses SQLite's online backup facility, so it is safe
  whether or not the app process is running, and it does not depend on the app,
  its supervisor, Tailscale, or an open terminal — automatic app start-on-boot
  is NOT a prerequisite for this task.

  Task settings:
    * Principal  : the invoking user, LogonType S4U (runs with no interactive
                   logon, no stored password). If WSL refuses to start under S4U
                   on your host, re-run with -LogonType Password (you will be
                   prompted once) — see the runbook.
    * Trigger    : daily at -Time (local host time), with StartWhenAvailable so a
                   run missed while the machine was off is taken at next wake.
    * Bounded    : ExecutionTimeLimit 1h, MultipleInstances = IgnoreNew, so a
                   slow or overlapping run cannot pile up. deploy/backup-run.sh
                   also bounds the snapshot itself (RECIPE_DEPLOY_BACKUP_TIMEOUT).
    * Idempotent : re-running replaces the existing task of the same name
                   (-Force), so repeated setup never leaves duplicates.

  This script only configures Task Scheduler. Backup schedule, destination,
  permissions, and diagnostics are documented in README "Operating the server"
  runbook 12. Freshness/age reporting and retention pruning are ticket 07b.

.PARAMETER Distro
  The WSL distribution the deployment runs in (wsl.exe -d value). Match
  RECIPE_DEPLOY_WSL_DISTRO in deploy/deploy.env.

.PARAMETER Checkout
  Absolute path to the repository checkout *inside WSL* (e.g. /home/you/recipe).
  Match RECIPE_DEPLOY_CHECKOUT. Use a path without spaces.

.PARAMETER Time
  Daily run time, "HH:mm" local host time. Default 03:30.

.PARAMETER TaskName
  Scheduled Task name. Default "RecipeAppDailyBackup".

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
      wsl.exe -d <Distro> -- bash <Checkout>/deploy/backup-run.sh

.EXAMPLE
  .\deploy\windows\register-backup-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe

.EXAMPLE
  .\deploy\windows\register-backup-task.ps1 -Distro Ubuntu -Checkout /home/you/recipe -Unregister
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string] $Distro,
  [Parameter(Mandatory = $true)] [string] $Checkout,
  [string] $Time = "03:30",
  [string] $TaskName = "RecipeAppDailyBackup",
  [string] $Bash = "bash",
  [string] $WslPath = "wsl.exe",
  [ValidateSet("S4U", "Password")] [string] $LogonType = "S4U",
  [switch] $Unregister,
  [switch] $ShowCommand
)

$ErrorActionPreference = "Stop"

# backup-run.sh sources deploy/lib.sh by its own path, so the working directory
# does not matter; pass an absolute script path, single-quoted for the WSL-side
# shell so a space in $Checkout does not split it.
$scriptPath = "$Checkout/deploy/backup-run.sh"
$wslArgs = "-d $Distro -- $Bash '$scriptPath'"

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

$trigger = New-ScheduledTaskTrigger -Daily -At $Time

# StartWhenAvailable: take a run missed while the machine was off. Host power
# behaviour (battery, sleep) is spec item 24 / a separate concern, left at the
# Task Scheduler defaults here.
$settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
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
  -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
  -Description "Daily unattended SQLite backup for the recipe household deployment (ticket 07a). Runs deploy/backup-run.sh in WSL '$Distro'." `
  -Force | Out-Null

Write-Host "registered scheduled task '$TaskName'"
Write-Host "  runs   : daily at $Time (host local time), StartWhenAvailable, ExecutionTimeLimit 1h"
Write-Host "  logon  : $LogonType (runs with no user signed in)"
Write-Host "  command: $WslPath $wslArgs"
Write-Host ""
Write-Host "verify now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "then check the newest snapshot in RECIPE_DEPLOY_BACKUP_DIR and the last"
Write-Host "line of the backup run log (RECIPE_DEPLOY_RUNTIME_DIR/backup-runs.log)."
Write-Host ""
Get-ScheduledTaskInfo -TaskName $TaskName |
  Format-List TaskName, LastRunTime, LastTaskResult, NextRunTime
