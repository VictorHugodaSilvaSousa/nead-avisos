# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
# Instalador do NEAD Avisos para Windows: um comando, sem precisar de administrador nem de Python.
#
#   irm https://raw.githubusercontent.com/VictorHugodaSilvaSousa/nead-avisos/main/instalar.ps1 | iex
#
# O que ele faz:
#   1. baixa a versão mais recente do NEAD-Avisos.exe (página de versões do GitHub);
#   2. confere o SHA-256 publicado junto (se não bater, NÃO instala);
#   3. instala em %LOCALAPPDATA%\NEAD-Avisos (só para o seu usuário);
#   4. cria atalhos no Menu Iniciar e na Área de Trabalho;
#   5. abre o assistente de configuração.
# Para remover:  & "$env:LOCALAPPDATA\NEAD-Avisos\instalar.ps1" -Desinstalar   (ou: nead-avisos apagar-tudo)

param(
    [switch]$SemAssistente,
    [switch]$SemAtalhos,          # para testes: não cria atalhos
    [switch]$Desinstalar,
    [string]$Destino = (Join-Path $env:LOCALAPPDATA 'NEAD-Avisos'),
    [string]$Versao = 'latest'
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$repo = 'VictorHugodaSilvaSousa/nead-avisos'
$atalhos = @(
    (Join-Path ([Environment]::GetFolderPath('Programs')) 'NEAD Avisos.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'NEAD Avisos.lnk')
)

function Passo($texto) { Write-Host "`n==> $texto" -ForegroundColor Cyan }

if ($Desinstalar) {
    Passo 'Removendo o NEAD Avisos deste usuário'
    $exe = Join-Path $Destino 'NEAD-Avisos.exe'
    if (Test-Path $exe) { & $exe apagar-tudo }
    $atalhos | ForEach-Object { Remove-Item $_ -ErrorAction SilentlyContinue }
    Remove-Item $Destino -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host 'Pronto: programa, atalhos e dados removidos.' -ForegroundColor Green
    return
}

Write-Host 'NEAD Avisos — avisos do Moodle do NEAD no seu Telegram' -ForegroundColor Green
Write-Host 'Somente leitura no Moodle; sua senha não é guardada. Detalhes: SECURITY.md no GitHub.'

$base = if ($Versao -eq 'latest') { "https://github.com/$repo/releases/latest/download" }
        else { "https://github.com/$repo/releases/download/$Versao" }
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("nead-avisos-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    Passo 'Baixando a versão mais recente'
    Invoke-WebRequest -UseBasicParsing "$base/NEAD-Avisos.exe" -OutFile (Join-Path $tmp 'NEAD-Avisos.exe')
    Invoke-WebRequest -UseBasicParsing "$base/NEAD-Avisos.exe.sha256" -OutFile (Join-Path $tmp 'esperado.sha256')

    Passo 'Conferindo a integridade do arquivo (SHA-256)'
    $esperado = ((Get-Content (Join-Path $tmp 'esperado.sha256') -Raw).Trim() -split '\s+')[0].ToLower()
    $obtido = (Get-FileHash (Join-Path $tmp 'NEAD-Avisos.exe') -Algorithm SHA256).Hash.ToLower()
    if ($esperado -ne $obtido) {
        throw "O arquivo baixado não confere com o publicado (esperado $esperado, obtido $obtido). Nada foi instalado."
    }
    Write-Host "OK: $obtido"

    Passo "Instalando em $Destino"
    New-Item -ItemType Directory -Path $Destino -Force | Out-Null
    Move-Item (Join-Path $tmp 'NEAD-Avisos.exe') (Join-Path $Destino 'NEAD-Avisos.exe') -Force
    Unblock-File (Join-Path $Destino 'NEAD-Avisos.exe')     # integridade já conferida: sem o aviso do SmartScreen
    # Cópia do instalador para desinstalar depois. Gravada COM BOM: assim o PowerShell 5 lê os acentos do arquivo.
    # (No GitHub ele fica SEM BOM, porque o BOM quebra o 'irm | iex'.)
    $fonte = (Invoke-RestMethod "https://raw.githubusercontent.com/$repo/main/instalar.ps1").TrimStart([char]0xFEFF)
    [IO.File]::WriteAllText((Join-Path $Destino 'instalar.ps1'), $fonte, (New-Object Text.UTF8Encoding $true))

    Passo 'Criando atalhos (Menu Iniciar e Área de Trabalho)'
    $shell = New-Object -ComObject WScript.Shell
    foreach ($lnk in $(if ($SemAtalhos) { @() } else { $atalhos })) {
        $s = $shell.CreateShortcut($lnk)
        $s.TargetPath = Join-Path $Destino 'NEAD-Avisos.exe'
        $s.WorkingDirectory = $Destino
        $s.Description = 'NEAD Avisos: configurar e ver o status'
        $s.Save()
    }
} finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "`nInstalado! Atalho 'NEAD Avisos' no Menu Iniciar e na Área de Trabalho." -ForegroundColor Green
if (-not $SemAssistente) {
    Passo 'Abrindo o assistente de configuração'
    Push-Location $Destino
    try { & (Join-Path $Destino 'NEAD-Avisos.exe') assistente } finally { Pop-Location }
}
