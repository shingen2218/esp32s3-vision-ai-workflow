$ErrorActionPreference = "Continue"

$Printed = $false

try {
    $Ports = Get-CimInstance Win32_SerialPort -ErrorAction Stop
    foreach ($Port in $Ports) {
        Write-Host "$($Port.DeviceID) - $($Port.Name)"
        $Printed = $true
    }
} catch {
    Write-Host "[WARN] Get-CimInstance Win32_SerialPort failed: $($_.Exception.Message)"
}

try {
    $Names = [System.IO.Ports.SerialPort]::GetPortNames()
    foreach ($Name in $Names) {
        Write-Host "$Name"
        $Printed = $true
    }
} catch {
    Write-Host "[WARN] SerialPort.GetPortNames failed: $($_.Exception.Message)"
}

if (-not $Printed) {
    Write-Host "[NG] No serial ports found."
    exit 1
}
