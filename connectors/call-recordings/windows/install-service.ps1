# Registers the connector service. Do not run this on the production Windows
# Server until that installation is separately authorized. It does not copy,
# move, or edit recordings.
param(
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$Config
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Config)) { throw "Config file is missing" }
& $Python -m call_recordings service install --config $Config
if ($LASTEXITCODE -ne 0) { throw "Service registration failed" }
