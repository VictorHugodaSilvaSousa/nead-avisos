# Prepara o NEAD Avisos a partir do CÓDIGO (para quem vai mexer no programa ou rodar sem o .exe).
# Instala o que faltar e confere que tudo funciona:
#   1. Python 3.12 (pelo winget, se não houver Python 3.11 ou mais novo);
#   2. ambiente virtual .venv com as dependências nas versões testadas (constraints.txt);
#   3. roda os testes.
# Uso, na pasta do projeto:   powershell -ExecutionPolicy Bypass -File scripts\instalar-codigo.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Passo($texto) { Write-Host "`n==> $texto" -ForegroundColor Cyan }

function Find-Python {
    foreach ($cmd in @('py -3.12', 'py -3', 'python')) {
        try {
            $exe, $arg = $cmd -split ' ', 2
            $v = & $exe $arg -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$v -ge [version]'3.11') { return $cmd }
        } catch { }
    }
    return $null
}

Passo 'Procurando o Python 3.11 ou mais novo'
$py = Find-Python
if (-not $py) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Python 3.11+ não encontrado e o winget não está disponível. Instale o Python em https://www.python.org/downloads/ e rode de novo.'
    }
    Passo 'Instalando o Python 3.12 (winget, só para o seu usuário)'
    winget install --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $py = Find-Python
    if (-not $py) { throw 'O Python foi instalado, mas ainda não aparece. Feche e abra o PowerShell e rode de novo.' }
}
Write-Host "Usando: $py"

Passo 'Criando o ambiente virtual (.venv)'
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    $exe, $arg = $py -split ' ', 2
    & $exe $arg -m venv .venv
}

Passo 'Instalando as dependências (versões testadas)'
& .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .venv\Scripts\python.exe -m pip install --quiet -c constraints.txt -e . pytest

Passo 'Rodando os testes'
& .venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Algum teste falhou: veja acima.' }

if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
Write-Host "`nPronto! Próximo passo: .venv\Scripts\nead-avisos assistente" -ForegroundColor Green
