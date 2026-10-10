# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
# Remove a tarefa "NEAD-Avisos" do Agendador. Não apaga configuração nem estado.
$t = Get-ScheduledTask -TaskName 'NEAD-Avisos' -ErrorAction SilentlyContinue
if ($t) { Unregister-ScheduledTask -TaskName 'NEAD-Avisos' -Confirm:$false; Write-Host 'Tarefa NEAD-Avisos removida.' }
else { Write-Host 'Tarefa NEAD-Avisos não existe.' }
