#!/bin/bash
# Live search-similar test using a real product image from Neon/CDN
set -euo pipefail
cd "$HOME/backend.everystore.pk/backend"
PHP=/opt/bitnami/php/bin/php
API_KEY=$(grep '^PRODUCT_MATCH_API_KEY=' .env | cut -d= -f2- | tr -d '"')
API_URL=$(grep '^PRODUCT_MATCH_URL=' .env | grep -v '^#' | cut -d= -f2-)

cat > /tmp/pm_match_pick.php <<'PHP'
<?php
require '/home/bitnami/backend.everystore.pk/backend/vendor/autoload.php';
$app = require '/home/bitnami/backend.everystore.pk/backend/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Product;
use App\Services\MediaService;

// Prefer an INDEXED product with images (already in vector DB)
$p = Product::query()
    ->where('ai_status', 'INDEXED')
    ->whereHas('images')
    ->with(['images' => fn ($q) => $q->orderBy('order')->orderBy('id')])
    ->orderByDesc('updated_at')
    ->first();

if (!$p) {
    $p = Product::query()
        ->whereHas('images')
        ->with(['images' => fn ($q) => $q->orderBy('order')->orderBy('id')])
        ->orderByDesc('updated_at')
        ->first();
}

if (!$p || !$p->image) {
    fwrite(STDERR, "No product image found\n");
    exit(1);
}

$url = MediaService::uploadUrl('products/' . $p->image);
echo json_encode([
    'id' => $p->id,
    'title' => $p->title,
    'ai_status' => (string) ($p->ai_status?->value ?? $p->ai_status),
    'image' => $p->image,
    'url' => $url,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), PHP_EOL;
PHP

echo "=== pick indexed product image ==="
META=$($PHP /tmp/pm_match_pick.php)
echo "$META"
PRODUCT_ID=$(echo "$META" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
IMG_URL=$(echo "$META" | python3 -c 'import sys,json; print(json.load(sys.stdin)["url"])')

TMP=/tmp/pm_match_query.jpg
echo "=== download image ==="
curl -sS -L --max-time 30 -o "$TMP" "$IMG_URL"
file "$TMP" || true
ls -la "$TMP"

echo "=== POST /products/search-similar (Lambda) ==="
curl -sS --max-time 180 -X POST "$API_URL/products/search-similar" \
  -H "X-Internal-API-Key: $API_KEY" \
  -F "image_file=@${TMP};type=image/jpeg" \
  -F "top_k=10" | tee /tmp/pm_match_result.json
echo

echo "=== via Laravel ProductMatchService ==="
cat > /tmp/pm_match_laravel.php <<PHP
<?php
require '/home/bitnami/backend.everystore.pk/backend/vendor/autoload.php';
\$app = require '/home/bitnami/backend.everystore.pk/backend/bootstrap/app.php';
\$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

\$tmp = '/tmp/pm_match_query.jpg';
\$uploaded = new Illuminate\Http\UploadedFile(\$tmp, 'query.jpg', 'image/jpeg', null, true);
\$result = App\Services\ProductMatchService::searchSimilar(\$uploaded, 10);
echo json_encode(\$result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), PHP_EOL;
PHP
$PHP /tmp/pm_match_laravel.php | tee /tmp/pm_match_laravel.json

echo "=== summary ==="
python3 - <<PY
import json
from pathlib import Path
raw = Path("/tmp/pm_match_result.json").read_text()
data = json.loads(raw)
print(f"query_product_id={$PRODUCT_ID}")
print(f"count={data.get('count')}")
for m in data.get("matches", []):
    mark = " <== SELF" if str(m.get("product_id")) == str($PRODUCT_ID) else ""
    print(f"  product_id={m.get('product_id')} score={m.get('score'):.4f} title={m.get('metadata',{}).get('title','')}{mark}")
PY
