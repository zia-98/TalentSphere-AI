<#
run_all.ps1
Convenience script to setup environment and run the full project on Windows (PowerShell).

Usage:
  PowerShell -ExecutionPolicy Bypass -File .\run_all.ps1 [-SkipTests] [-SkipPPT] [-SkipInstall]

By default the script will:
 - create a virtual environment at `.venv` (if missing)
 - install packages from `requirements.txt`
 - run unit tests (pytest)
 - run the pipeline (`python src/main.py`)
 - generate the presentation (`python presentation/generate_pptx.py`)

Options:
 -SkipTests  : do not run pytest
 -SkipPPT    : do not generate the PPTX
 -SkipInstall: skip `pip install -r requirements.txt`
#>

param(
    [switch]$SkipTests = $false,
    [switch]$SkipPPT = $false,
    [switch]$SkipInstall = $false
)

$ErrorActionPreference = 'Stop'
$projRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $projRoot

Write-Host "== TalentSphere AI: run_all starting ===" -ForegroundColor Cyan

# 1) Create venv if missing
$venvPath = Join-Path $projRoot ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath" -ForegroundColor Green
    python -m venv .venv
} else {
    Write-Host "Using existing virtual environment: $venvPath" -ForegroundColor Yellow
}

$python = Join-Path $venvPath "Scripts\python.exe"
$pip = Join-Path $venvPath "Scripts\pip.exe"
$pytestExe = Join-Path $venvPath "Scripts\pytest.exe"

if (-not (Test-Path $python)) {
    Write-Host "Warning: Virtualenv python not found. Falling back to system 'python'" -ForegroundColor Yellow
    $python = "python"
    $pip = "pip"
}

# 2) Install dependencies
if (-not $SkipInstall) {
    if (Test-Path "$projRoot\requirements.txt") {
        Write-Host "Installing dependencies from requirements.txt" -ForegroundColor Green
        & $pip install -r requirements.txt
    } else {
        Write-Host "No requirements.txt found; skipping install" -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping dependency installation (-SkipInstall)" -ForegroundColor Yellow
}

# 3) Run unit tests
if (-not $SkipTests) {
    Write-Host "Running unit tests (pytest)" -ForegroundColor Green
    # Use venv pytest if available
    if (Test-Path $pytestExe) {
        & $pytestExe tests -q
    } else {
        & $python -m pytest tests -q
    }
} else {
    Write-Host "Skipping tests (-SkipTests)" -ForegroundColor Yellow
}

# 4) Run pipeline
Write-Host "Running pipeline: python src/main.py" -ForegroundColor Green
& $python src/main.py

# 5) Generate presentation
if (-not $SkipPPT) {
    Write-Host "Generating PPTX" -ForegroundColor Green
    & $python presentation\generate_pptx.py
} else {
    Write-Host "Skipping PPTX generation (-SkipPPT)" -ForegroundColor Yellow
}

Write-Host "== run_all completed ===" -ForegroundColor Cyan

Pop-Location
