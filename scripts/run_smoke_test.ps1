$ErrorActionPreference = "Stop"

$VersionOutput = python --version
$PythonPath = (Get-Command python).Source

Write-Host $VersionOutput
Write-Host "Python executable: $PythonPath"

if ($VersionOutput -notmatch "Python 3\.12\.") {
    Write-Error "Python 3.12.x is required for this project. Fix PATH so python points to Python312."
}

if ($PythonPath -match "Python314") {
    Write-Error "Python314 is on the active python path. Fix PATH so Python312 is used first."
}

python -m pip install -r server\requirements.txt
python scripts\check_project_structure.py
python -m compileall server tools scripts
python scripts\smoke_test_server.py
