param(
    [Parameter(Mandatory = $true)]
    [string]$ApiKey,
    [string]$Root = "C:\Users\smh_2\Desktop\result",
    [int]$MaxWorkers = 5,
    [double]$TimeoutSec = 8,
    [int]$ChunkSize = 20,
    [int]$LimitPerMethod = 0
)

$ErrorActionPreference = "Stop"

$models = @("gpt-5.2", "gemini-3.1-pro", "gpt-4o")
$baseOut = Join-Path $Root "mechanism_outputs\jailbreak_api"
$logDir = Join-Path $baseOut "logs"

New-Item -ItemType Directory -Path $baseOut -Force | Out-Null
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$env:JAILBREAK_API_KEY = $ApiKey

$started = @()
foreach ($model in $models) {
    $outLog = Join-Path $logDir "$model.out.log"
    $errLog = Join-Path $logDir "$model.err.log"
    if (Test-Path $outLog) { Remove-Item $outLog -Force }
    if (Test-Path $errLog) { Remove-Item $errLog -Force }

    $argList = @(
        "build_jailbreak_api_labels.py",
        "--model-id", $model,
        "--max-workers", "$MaxWorkers",
        "--timeout-sec", "$TimeoutSec",
        "--chunk-size", "$ChunkSize"
    )
    if ($LimitPerMethod -gt 0) {
        $argList += @("--limit-per-method", "$LimitPerMethod")
    }

    $proc = Start-Process `
        -FilePath "python" `
        -WorkingDirectory $Root `
        -ArgumentList $argList `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -PassThru

    $started += [PSCustomObject]@{
        model = $model
        pid = $proc.Id
        out_log = $outLog
        err_log = $errLog
    }
}

Write-Host "Started 3 jobs:" -ForegroundColor Green
$started | Format-Table -AutoSize
Write-Host ""
Write-Host "Watch logs:" -ForegroundColor Cyan
Write-Host "Get-Content '$logDir\gpt-5.2.out.log' -Wait"
Write-Host "Get-Content '$logDir\gemini-3.1-pro.out.log' -Wait"
Write-Host "Get-Content '$logDir\gpt-4o.out.log' -Wait"
