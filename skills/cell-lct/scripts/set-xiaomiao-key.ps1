#requires -Version 5.1

[CmdletBinding()]
param(
    [string]$SecretPath = "$env:USERPROFILE\.codex\secrets\xiaomiao-api-key.dpapi"
)

Write-Host "Cell-lct Free uses 100% local offline vectorization (vtracer). No API key is needed!" -ForegroundColor Green
[pscustomobject]@{
    ok = $true
    mode = "offline-free"
    message = "No API key required."
} | ConvertTo-Json -Compress
