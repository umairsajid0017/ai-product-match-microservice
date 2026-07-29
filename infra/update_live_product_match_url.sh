#!/bin/bash
set -euo pipefail
ENV="$HOME/backend.everystore.pk/backend/.env"
cp -a "$ENV" "$ENV.bak.$(date +%Y%m%d%H%M%S)"

python3 - <<'PY'
from pathlib import Path
path = Path.home() / "backend.everystore.pk/backend/.env"
lines = path.read_text().splitlines()
out = []
done = False
for line in lines:
    if line.startswith("PRODUCT_MATCH_URL=") and not done:
        out.append("# " + line + "  # old Lightsail product-match")
        out.append("PRODUCT_MATCH_URL=https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com")
        done = True
    elif line.startswith("# PRODUCT_MATCH_URL=") and "old Lightsail" in line:
        out.append(line)
    else:
        out.append(line)
if not done:
    # already commented-only? ensure active new URL exists
    joined = "\n".join(out)
    if "0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com" not in joined:
        raise SystemExit("PRODUCT_MATCH_URL not found / not updated")
path.write_text("\n".join(out) + "\n")
print("updated")
PY

echo "=== PRODUCT_MATCH lines ==="
grep -n "PRODUCT_MATCH" "$ENV"

PHP_BIN="/opt/bitnami/php/bin/php"
if [ ! -x "$PHP_BIN" ]; then PHP_BIN="$(command -v php)"; fi
echo "PHP=$PHP_BIN"
cd "$HOME/backend.everystore.pk/backend"
"$PHP_BIN" artisan config:clear || true
"$PHP_BIN" -r 'require "vendor/autoload.php"; $app=require "bootstrap/app.php"; $app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap(); echo config("services.product_match.url"), PHP_EOL;' || true
