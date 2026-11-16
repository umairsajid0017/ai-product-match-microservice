<#
.SYNOPSIS
    Deploy Everystore product-match to Google Cloud Run (backup serverless deployment).

.EXAMPLE
    $env:DATABASE_URL = "postgresql://..."
    $env:INTERNAL_API_KEY = "..."
    .\infra\deploy-cloudrun.ps1
#>

param(
    [string]$ProjectId = "everystore-4c228",
    [string]$Region = "asia-southeast1",
    [string]$ServiceName = "everystore-product-match",
    [string]$RepoName = "product-match",
    [string]$ImageTag = "latest",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Push-Location $RootDir

try {
    Write-Host "1. Ensuring Artifact Registry repository '$RepoName' exists in $Region..." -ForegroundColor Cyan
    $repoExists = gcloud artifacts repositories list --location=$Region --project=$ProjectId --filter="name:$RepoName" --format="value(name)"
    if (-not $repoExists) {
        gcloud artifacts repositories create $RepoName `
            --repository-format=docker `
            --location=$Region `
            --description="Everystore product-match container images" `
            --project=$ProjectId
        if ($LASTEXITCODE -ne 0) { throw "Failed to create Artifact Registry repository." }
    }

    $ImageUri = "$Region-docker.pkg.dev/$ProjectId/$RepoName/${ServiceName}:$ImageTag"
    if (-not $SkipBuild) {
        Write-Host "2. Building and pushing image $ImageUri via Cloud Build..." -ForegroundColor Cyan

        $CloudBuildConfig = Join-Path $env:TEMP "cloudbuild-product-match-$([guid]::NewGuid().ToString('N')).yaml"
        @"
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-f', 'Dockerfile.cloudrun', '-t', '$ImageUri', '.']
images:
  - '$ImageUri'
"@ | Set-Content -Path $CloudBuildConfig -Encoding UTF8

        try {
            gcloud builds submit . `
                --config=$CloudBuildConfig `
                --project=$ProjectId
            if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed." }
        } finally {
            Remove-Item -Path $CloudBuildConfig -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "2. Skipping Cloud Build (-SkipBuild); using $ImageUri" -ForegroundColor Cyan
    }

    Write-Host "3. Syncing secrets to Secret Manager (if env vars provided)..." -ForegroundColor Cyan
    if ($env:DATABASE_URL) {
        $tmpDb = New-TemporaryFile
        try {
            [System.IO.File]::WriteAllText($tmpDb.FullName, $env:DATABASE_URL.Trim())
            $exists = gcloud secrets list --project=$ProjectId --filter="name:product-match-database-url" --format="value(name)"
            if (-not $exists) {
                gcloud secrets create product-match-database-url --replication-policy=automatic --project=$ProjectId
            }
            gcloud secrets versions add product-match-database-url --data-file="$($tmpDb.FullName)" --project=$ProjectId | Out-Null
        } finally {
            Remove-Item $tmpDb.FullName -Force -ErrorAction SilentlyContinue
        }
    }

    if ($env:INTERNAL_API_KEY) {
        $tmpKey = New-TemporaryFile
        try {
            [System.IO.File]::WriteAllText($tmpKey.FullName, $env:INTERNAL_API_KEY.Trim())
            $exists = gcloud secrets list --project=$ProjectId --filter="name:product-match-internal-api-key" --format="value(name)"
            if (-not $exists) {
                gcloud secrets create product-match-internal-api-key --replication-policy=automatic --project=$ProjectId
            }
            gcloud secrets versions add product-match-internal-api-key --data-file="$($tmpKey.FullName)" --project=$ProjectId | Out-Null
        } finally {
            Remove-Item $tmpKey.FullName -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Host "4. Granting Cloud Run runtime service account access to secrets..." -ForegroundColor Cyan
    $ProjectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
    $RuntimeSa = "$ProjectNumber-compute@developer.gserviceaccount.com"
    foreach ($secret in @("product-match-database-url", "product-match-internal-api-key")) {
        gcloud secrets add-iam-policy-binding $secret `
            --member="serviceAccount:$RuntimeSa" `
            --role="roles/secretmanager.secretAccessor" `
            --project=$ProjectId `
            --quiet | Out-Null
    }

    Write-Host "5. Deploying Cloud Run service '$ServiceName' (min-instances=0)..." -ForegroundColor Cyan
    gcloud run deploy $ServiceName `
        --image=$ImageUri `
        --project=$ProjectId `
        --region=$Region `
        --platform=managed `
        --allow-unauthenticated `
        --min-instances=0 `
        --max-instances=5 `
        --memory=4Gi `
        --cpu=2 `
        --timeout=120 `
        --no-cpu-throttling `
        --set-secrets="DATABASE_URL=product-match-database-url:latest,INTERNAL_API_KEY=product-match-internal-api-key:latest" `
        --set-env-vars="LARAVEL_CALLBACK_URL=https://backend.everystore.pk/api/internal/ai-matching/callback,ALLOWED_IMAGE_HOSTS=cdn.everystore.pk,SIMILARITY_THRESHOLD=0.70,DEFAULT_TOP_K=10,CLIP_MODEL_NAME=ViT-B-32,CLIP_PRETRAINED=openai"
    if ($LASTEXITCODE -ne 0) { throw "Cloud Run deploy failed." }

    $ServiceUrl = gcloud run services describe $ServiceName --region=$Region --project=$ProjectId --format="value(status.url)"
    Write-Host "`nDeployed successfully! Backup URL: $ServiceUrl" -ForegroundColor Green
} finally {
    Pop-Location
}
