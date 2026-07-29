# Deploy everystore-product-match to AWS (ap-south-1)
# Prerequisites: AWS CLI + Docker + SAM CLI
# Secrets live in SSM:
#   /everystore/product-match/database-url
#   /everystore/product-match/internal-api-key
#
# Usage:
#   $env:DATABASE_URL = 'postgresql://...'
#   $env:INTERNAL_API_KEY = '...'
#   .\infra\deploy.ps1

$ErrorActionPreference = "Stop"
$InfraDir = $PSScriptRoot
Set-Location $InfraDir

$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
  [System.Environment]::GetEnvironmentVariable("Path","User") + ";" +
  "$env:APPDATA\Python\Python314\Scripts"

if (-not $env:DATABASE_URL) { throw "Set DATABASE_URL" }
if (-not $env:INTERNAL_API_KEY) { throw "Set INTERNAL_API_KEY" }
$env:DATABASE_URL = $env:DATABASE_URL.Trim().Trim('"').Trim("'")
if (-not $env:LARAVEL_CALLBACK_URL) {
  $env:LARAVEL_CALLBACK_URL = "https://backend.everystore.pk/api/internal/ai-matching/callback"
}

Write-Host "==> Upsert SSM secrets (ap-south-1)"
aws ssm put-parameter --region ap-south-1 --name /everystore/product-match/database-url --type String --value $env:DATABASE_URL --overwrite | Out-Null
aws ssm put-parameter --region ap-south-1 --name /everystore/product-match/internal-api-key --type String --value $env:INTERNAL_API_KEY --overwrite | Out-Null

Write-Host "==> Neon migration"
python .\run_migration.py

Write-Host "==> sam build"
sam build --use-container --template template.yaml

Write-Host "==> sam deploy"
sam deploy `
  --stack-name everystore-product-match `
  --region ap-south-1 `
  --capabilities CAPABILITY_IAM `
  --resolve-image-repos `
  --no-confirm-changeset `
  --no-fail-on-empty-changeset `
  --parameter-overrides "LaravelCallbackUrl=$($env:LARAVEL_CALLBACK_URL)"

Write-Host "==> Stack outputs"
aws cloudformation describe-stacks `
  --stack-name everystore-product-match `
  --region ap-south-1 `
  --query "Stacks[0].Outputs" `
  --output table

Write-Host "==> Smoke test"
$env:PRODUCT_MATCH_URL = (
  aws cloudformation describe-stacks --stack-name everystore-product-match --region ap-south-1 `
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text
)
python .\smoke_test.py
