#requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("health", "verify", "upload", "status", "download")]
    [string]$Action = "health",

    [string]$ImagePath,
    [string]$ImageId,
    [string]$OutputPath,
    [uri]$BaseUrl = "http://localhost",
    [string]$SecretPath = ""
)

switch ($Action) {
    "health" {
        [pscustomobject]@{
            ok = $true
            status = "healthy"
            mode = "local-free"
        }
    }
    "verify" {
        [pscustomobject]@{
            ok = $true
            authenticated = $true
            service = "local-vtracer-free"
            credits_charged = 0
            credits_left = 999999
        }
    }
    default {
        [pscustomobject]@{
            ok = $true
            mode = "local-free"
        }
    }
}
