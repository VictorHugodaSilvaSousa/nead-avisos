# Cria (ou atualiza) a tarefa "NEAD-Avisos": verifica o Moodle a cada 15 minutos enquanto o PC estiver ligado.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\install-windows-schedule.ps1 [-Minutos 15]
# Remover: powershell -ExecutionPolicy Bypass -File scripts\uninstall-windows-schedule.ps1
# Se a versão na nuvem (GitHub Actions) estiver ativa, NÃO use as duas ao mesmo tempo (os avisos sairiam em dobro).

param([int]$Minutos = 15)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$bat = Join-Path $PSScriptRoot 'run-avisos.bat'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $Minutos)
$action = New-ScheduledTaskAction -Execute "`"$bat`"" -WorkingDirectory $root
Register-ScheduledTask -TaskName 'NEAD-Avisos' -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description 'NEAD Avisos: novidades do Moodle no Telegram (somente leitura).' -Force | Out-Null
Get-ScheduledTask -TaskName 'NEAD-Avisos' | Select-Object TaskName, State,
    @{n = 'Próxima'; e = { (Get-ScheduledTaskInfo $_).NextRunTime } } | Format-Table -AutoSize
Write-Host "Tarefa criada: a cada $Minutos minutos. Log em data\avisos.log"
