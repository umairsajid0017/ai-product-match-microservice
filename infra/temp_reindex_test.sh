#!/bin/bash
# Temp AI match reindex test on Everystore live server
set -euo pipefail
cd "$HOME/backend.everystore.pk/backend"
PHP=/opt/bitnami/php/bin/php
export PATH="/opt/bitnami/php/bin:$PATH"

API_KEY=$(grep '^PRODUCT_MATCH_API_KEY=' .env | cut -d= -f2- | tr -d '"')
API_URL=$(grep '^PRODUCT_MATCH_URL=' .env | grep -v '^#' | cut -d= -f2-)

echo "=== service URL / health ==="
echo "$API_URL"
curl -sS -m 15 "$API_URL/health"; echo
curl -sS -m 15 -H "X-Internal-API-Key: $API_KEY" "$API_URL/queue/status"; echo

cat > /tmp/pm_pick.php <<'PHP'
<?php
require __DIR__ . '/../home/bitnami/backend.everystore.pk/backend/vendor/autoload.php';
PHP

# Run pick via artisan script file to avoid shell escaping
cat > /tmp/pm_dispatch.php <<'PHP'
<?php
use App\Models\Product;
use App\Enums\ProductAiStatus;
use App\Jobs\IndexProductImagesJob;

require '/home/bitnami/backend.everystore.pk/backend/vendor/autoload.php';
$app = require '/home/bitnami/backend.everystore.pk/backend/bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();

$items = Product::query()
    ->whereHas('images')
    ->with(['images' => fn ($q) => $q->orderBy('order')->orderBy('id')])
    ->orderByDesc('updated_at')
    ->limit(5)
    ->get(['id', 'title', 'ai_status', 'updated_at']);

foreach ($items as $p) {
    echo $p->id . '|' . $p->title . '|' . (string) ($p->ai_status?->value ?? $p->ai_status) . '|' . ($p->images->first()?->name ?? '') . PHP_EOL;
}

$product = $items->first();
if (!$product) {
    fwrite(STDERR, "No product found\n");
    exit(1);
}

$product->ai_status = ProductAiStatus::UNINDEXED;
$product->save();
IndexProductImagesJob::dispatch($product->id);
echo 'DISPATCHED=' . $product->id . PHP_EOL;
PHP

echo "=== pick + dispatch (same as Re-index) ==="
$PHP /tmp/pm_dispatch.php | tee /tmp/pm_products.txt
PRODUCT_ID=$(grep '^DISPATCHED=' /tmp/pm_products.txt | cut -d= -f2)
echo "PRODUCT_ID=$PRODUCT_ID"

echo "=== redis ai-matching depth ==="
redis-cli llen everystore-database-queues:ai-matching || true

echo "=== process ai-matching jobs (up to 5) — note: no PM2 worker for this queue ==="
for n in 1 2 3 4 5; do
  echo "-- queue:work #$n --"
  $PHP artisan queue:work redis --queue=ai-matching --once --tries=3 --timeout=120 -v || true
done

echo "=== lambda queue after jobs ==="
curl -sS -m 20 -H "X-Internal-API-Key: $API_KEY" "$API_URL/queue/status"; echo

echo "=== monitor product ai_status ==="
cat > /tmp/pm_status.php <<PHP
<?php
require '/home/bitnami/backend.everystore.pk/backend/vendor/autoload.php';
\$app = require '/home/bitnami/backend.everystore.pk/backend/bootstrap/app.php';
\$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
\$p = App\Models\Product::with('images')->find($PRODUCT_ID);
echo json_encode([
  'id' => \$p->id,
  'title' => \$p->title,
  'ai_status' => (string) (\$p->ai_status?->value ?? \$p->ai_status),
  'image' => \$p->image,
  'images_count' => \$p->images->count(),
], JSON_PRETTY_PRINT), PHP_EOL;
PHP

for i in $(seq 1 15); do
  sleep 8
  STATUS=$($PHP /tmp/pm_status.php | python3 -c 'import sys,json; print(json.load(sys.stdin)["ai_status"])')
  echo "poll $i ai_status=$STATUS"
  case "$STATUS" in
    INDEXED|FAILED) break ;;
  esac
done

echo "=== final product ==="
$PHP /tmp/pm_status.php

echo "=== laravel log snippets ==="
grep -E "product ID: ${PRODUCT_ID}|Successfully indexed|Failed to index|Failed to create embedding|Starting background product" storage/logs/laravel.log | tail -n 50 || true

echo "=== lambda dead letters ==="
curl -sS -m 20 -H "X-Internal-API-Key: $API_KEY" "$API_URL/queue/dead-letters"; echo

echo "=== redis remaining ==="
redis-cli llen everystore-database-queues:ai-matching || true
