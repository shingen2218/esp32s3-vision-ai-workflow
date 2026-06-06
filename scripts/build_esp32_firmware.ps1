param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Invoke-Idf {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    $IdfCommand = Get-Command idf.py -ErrorAction SilentlyContinue
    if ($IdfCommand) {
        & $IdfCommand.Source @Arguments
        return
    }

    if ($env:IDF_PATH) {
        $IdfPy = Join-Path $env:IDF_PATH "tools\idf.py"
        if (Test-Path $IdfPy) {
            $IdfPython = $null
            if ($env:IDF_PYTHON_ENV_PATH) {
                $Candidate = Join-Path $env:IDF_PYTHON_ENV_PATH "Scripts\python.exe"
                if (Test-Path $Candidate) {
                    $IdfPython = $Candidate
                }
            }
            if (-not $IdfPython) {
                $IdfPython = "python"
            }
            & $IdfPython $IdfPy @Arguments
            return
        }
    }

    Write-Error "idf.py not found. Open an ESP-IDF PowerShell before running this script."
}

if (-not $env:IDF_PATH) {
    Write-Error "IDF_PATH is not set. Open an ESP-IDF PowerShell before running this script."
}

$Projects = @(
    "firmware\capture_upload",
    "firmware\inference_classification"
)

foreach ($Project in $Projects) {
    $ProjectPath = Join-Path $Root $Project
    Write-Host ""
    Write-Host "Building $Project"
    Push-Location $ProjectPath
    try {
        if ($Clean) {
            Write-Host "Running fullclean for $Project"
            Invoke-Idf fullclean
        }
        $Sdkconfig = Join-Path $ProjectPath "sdkconfig"
        $TargetIsSet = (Test-Path $Sdkconfig) -and ((Get-Content $Sdkconfig -Raw) -match 'CONFIG_IDF_TARGET="esp32s3"')
        if ($TargetIsSet) {
            Write-Host "Target already set to esp32s3"
        } else {
            Invoke-Idf set-target esp32s3
        }
        Invoke-Idf build
        Write-Host "[OK] $Project build passed"
    } catch {
        Write-Host "[NG] $Project build failed"
        throw
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "ESP32 firmware build passed."
