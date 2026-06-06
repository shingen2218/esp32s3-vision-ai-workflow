$ErrorActionPreference = "Stop"

function Write-Ok($Message) {
    Write-Host "[OK] $Message"
}

function Write-Ng($Message) {
    Write-Host "[NG] $Message"
    $script:Failed = $true
}

$Failed = $false
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

$IdfCommand = Get-Command idf.py -ErrorAction SilentlyContinue
if ($IdfCommand) {
    Write-Ok "idf.py found: $($IdfCommand.Source)"
} elseif ($env:IDF_PATH -and (Test-Path (Join-Path $env:IDF_PATH "tools\idf.py"))) {
    Write-Ok "idf.py found via IDF_PATH: $(Join-Path $env:IDF_PATH "tools\idf.py")"
} else {
    Write-Ng "idf.py not found. Open an ESP-IDF PowerShell or add it to PATH."
}

foreach ($Command in @("cmake", "ninja")) {
    $Found = Get-Command $Command -ErrorAction SilentlyContinue
    if ($Found) {
        Write-Ok "$Command found: $($Found.Source)"
    } else {
        Write-Ng "$Command not found. Open an ESP-IDF PowerShell or add it to PATH."
    }
}

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCommand) {
    try {
        $PythonVersion = & $PythonCommand.Source --version
        if ($PythonVersion -match "Python 3\.12\.") {
            Write-Ok "$PythonVersion ($($PythonCommand.Source))"
        } else {
            Write-Ng "python is not Python 3.12: $PythonVersion ($($PythonCommand.Source))"
        }
    } catch {
        Write-Ng "python exists but failed to run: $($PythonCommand.Source). Detail: $($_.Exception.Message)"
    }
} else {
    Write-Ng "python not found"
}

if ($env:IDF_PATH) {
    Write-Ok "IDF_PATH = $env:IDF_PATH"
} else {
    Write-Ng "IDF_PATH is not set. Open an ESP-IDF PowerShell first."
}

foreach ($Path in @(
    "firmware\capture_upload",
    "firmware\inference_classification",
    "firmware\inference_classification\main\model_data.cc",
    "firmware\inference_classification\main\model_data.h"
)) {
    $FullPath = Join-Path $Root $Path
    if (Test-Path $FullPath) {
        Write-Ok "$Path exists"
    } else {
        Write-Ng "$Path missing"
    }
}

if ($Failed) {
    Write-Host ""
    Write-Host "ESP-IDF environment check failed."
    exit 1
}

Write-Host ""
Write-Host "ESP-IDF environment check passed."
