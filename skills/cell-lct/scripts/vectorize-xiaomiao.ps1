#requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputImage,

    [Parameter(Mandatory = $true)]
    [string]$OutputSvg,

    [ValidateRange(2, 60)]
    [int]$PollSeconds = 5,

    [ValidateRange(30, 3600)]
    [int]$TimeoutSeconds = 900,

    [ValidateRange(1, 1000000)]
    [int]$MaxCreditsWithoutConfirmation = 1,

    [ValidateRange(0, 1000000)]
    [int]$EstimatedCredits = 0,

    [switch]$ApproveHighCost,

    [uri]$BaseUrl = "http://localhost"
)

$localRunner = Join-Path $PSScriptRoot "vectorize-local.ps1"
& $localRunner -InputImage $InputImage -OutputSvg $OutputSvg
