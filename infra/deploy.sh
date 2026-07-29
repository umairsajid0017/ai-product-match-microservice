#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

: "${DATABASE_URL:?Set DATABASE_URL}"
: "${INTERNAL_API_KEY:?Set INTERNAL_API_KEY}"
DATABASE_URL="${DATABASE_URL%\"}"
DATABASE_URL="${DATABASE_URL#\"}"
LARAVEL_CALLBACK_URL="${LARAVEL_CALLBACK_URL:-https://backend.everystore.pk/api/internal/ai-matching/callback}"

echo "==> Upsert SSM secrets"
aws ssm put-parameter --region ap-south-1 --name /everystore/product-match/database-url --type String --value "$DATABASE_URL" --overwrite >/dev/null
aws ssm put-parameter --region ap-south-1 --name /everystore/product-match/internal-api-key --type String --value "$INTERNAL_API_KEY" --overwrite >/dev/null

echo "==> Neon migration"
python run_migration.py

echo "==> sam build"
sam build --use-container --template template.yaml

echo "==> sam deploy"
sam deploy \
  --stack-name everystore-product-match \
  --region ap-south-1 \
  --capabilities CAPABILITY_IAM \
  --resolve-image-repos \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --parameter-overrides "LaravelCallbackUrl=${LARAVEL_CALLBACK_URL}"

aws cloudformation describe-stacks \
  --stack-name everystore-product-match \
  --region ap-south-1 \
  --query "Stacks[0].Outputs" \
  --output table

export PRODUCT_MATCH_URL
PRODUCT_MATCH_URL=$(aws cloudformation describe-stacks --stack-name everystore-product-match --region ap-south-1 \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
python smoke_test.py
