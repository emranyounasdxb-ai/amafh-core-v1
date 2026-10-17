# Removes the connector service registration. It does not delete recordings or
# the metadata index. Do not run this against the production server unless that
# removal is separately authorized.
param([Parameter(Mandatory = $true)][string]$Python)
$ErrorActionPreference = "Stop"
& $Python -m call_recordings service stop
if ($LASTEXITCODE -ne 0) { throw "Service stop failed" }
& $Python -m call_recordings service uninstall
if ($LASTEXITCODE -ne 0) { throw "Service removal failed" }
