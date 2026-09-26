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

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$inputPath = (Resolve-Path -LiteralPath $InputImage).Path
$outputPath = [IO.Path]::GetFullPath($OutputSvg)
$outputDirectory = Split-Path -Parent $outputPath
if ($outputDirectory) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$localVectorizer = Join-Path $PSScriptRoot "local_vectorize.py"
$validator = Join-Path $PSScriptRoot "validate_vector_svg.py"

if (-not (Test-Path -LiteralPath $localVectorizer -PathType Leaf)) {
    throw "Missing local vectorizer script: $localVectorizer"
}

# Determine python command
$pythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$pythonArgs = if ($pythonCmd -eq "py") { @("-3", "-X", "utf8") } else { @("-X", "utf8") }

# Run local vectorization
Write-Verbose "Executing local vectorization for $inputPath"
$vectorizeArgs = $pythonArgs + @($localVectorizer, "--input", $inputPath, "--output", $outputPath)
& $pythonCmd @vectorizeArgs

if ($LASTEXITCODE -ne 0) {
    throw "Local vectorization failed. Ensure 'vtracer' is installed: pip install vtracer"
}

if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "Vectorized SVG was not created at: $outputPath"
}

# Validate generated SVG
if (Test-Path -LiteralPath $validator -PathType Leaf) {
    $valArgs = $pythonArgs + @($validator, "--svg", $outputPath)
    $validationOutput = & $pythonCmd @valArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "SVG validation reported non-blocking warnings: $validationOutput"
    }
}

[ordered]@{
    ok = $true
    image_id = "local-offline-free"
    output_svg = $outputPath
    credits_left = 999999
    provider = "vtracer-local-free"
} | ConvertTo-Json -Compress
