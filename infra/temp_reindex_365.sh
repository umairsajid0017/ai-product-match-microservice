#!/bin/bash
set -euo pipefail
cd "$HOME/backend.everystore.pk/backend"
PHP=/opt/bitnami/php/bin/php
API_KEY=$(grep '^PRODUCT_MATCH_API_KEY=' .env | cut -d= -f2- | tr -d '"')
API_URL=$(grep '^PRODUCT_MATCH_URL=' .env | grep -v '^#' | cut -d= -f2-)
PRODUCT_ID=365

cat > /tmp/pm_reindex_one.php <<PHP
<?php
require '/home/bitnami/backend.everystore.pk/backend/vendor/autoload.php';
\$app = require '/home/bitnami/backend.everystore.pk/backend/bootstrap/app.php';
\$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
\$p = App\Models\Product::with('images')->find($PRODUCT_ID);
\$p->ai_status = App\Enums\ProductAiStatus::UNINDEXED;
\$p->save();
# sync path - call service directly to avoid backlog
App\Services\ProductMatchService::indexProductImages(\$p);
echo json_encode([
  'id'=>\$p->id,
  'title'=>\$p->title,
  'images'=>\$p->images->count(),
  'first_url'=> App\Services\MediaService::uploadUrl('products/'.\$p->image),
], JSON_PRETTY_PRINT), PHP_EOL;
PHP

echo "=== direct index product $PRODUCT_ID (bypass redis backlog) ==="
$PHP /tmp/pm_reindex_one.php

echo "=== lambda queue ==="
curl -sS -m 30 -H "X-Internal-API-Key: $API_KEY" "$API_URL/queue/status"; echo

echo "=== wait for callback/status ==="
for i in $(seq 1 20); do
  sleep 6
  STATUS=$($PHP -r "
require 'vendor/autoload.php';
\$app=require 'bootstrap/app.php';
\$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
\$p=App\Models\Product::find($PRODUCT_ID);
echo (string)(\$p->ai_status?->value ?? \$p->ai_status);
")
  echo "poll $i ai_status=$STATUS"
  case "$STATUS" in INDEXED|FAILED) break ;; esac
done

echo "=== statuses 343 344 345 365 ==="
$PHP -r '
require "vendor/autoload.php";
$app=require "bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
foreach ([343,344,345,365] as $id) {
  $p=App\Models\Product::find($id);
  echo $id." ".(string)($p->ai_status?->value ?? $p->ai_status).PHP_EOL;
}
'

echo "=== laravel log for 365 ==="
grep -E "product ID: 365|product 365|create embedding for product 365" storage/logs/laravel.log | tail -n 30 || true
