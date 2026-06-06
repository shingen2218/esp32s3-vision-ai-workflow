$ErrorActionPreference = "Stop"

function Is-UsableIPv4($Address) {
    if (-not $Address) { return $false }
    if ($Address -eq "127.0.0.1") { return $false }
    if ($Address.StartsWith("169.254.")) { return $false }
    return $Address -match "^\d{1,3}(\.\d{1,3}){3}$"
}

$Candidates = @()

try {
    $Candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { Is-UsableIPv4 $_.IPAddress } |
        Select-Object InterfaceAlias, IPAddress
} catch {
    Write-Host "[WARN] Get-NetIPAddress failed, falling back to ipconfig."
}

if (-not $Candidates -or $Candidates.Count -eq 0) {
    $Ipconfig = ipconfig
    $Matches = $Ipconfig | Select-String -Pattern "IPv4.*?:\s*([0-9.]+)"
    foreach ($Match in $Matches) {
        $Ip = $Match.Matches[0].Groups[1].Value
        if (Is-UsableIPv4 $Ip) {
            $Candidates += [PSCustomObject]@{ InterfaceAlias = "ipconfig"; IPAddress = $Ip }
        }
    }
}

if (-not $Candidates -or $Candidates.Count -eq 0) {
    Write-Host "[NG] No usable LAN IPv4 address found."
    exit 1
}

Write-Host "IPv4 candidates for SERVER_UPLOAD_URL:"
foreach ($Candidate in $Candidates) {
    Write-Host "[OK] $($Candidate.InterfaceAlias): $($Candidate.IPAddress)"
    Write-Host "     #define SERVER_UPLOAD_URL `"http://$($Candidate.IPAddress):8000/api/images/upload`""
}
