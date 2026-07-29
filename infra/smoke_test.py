"""Smoke test the deployed product-match API."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

import httpx

API = os.environ.get(
    "PRODUCT_MATCH_URL",
    "https://0y6bdqfbmd.execute-api.ap-south-1.amazonaws.com",
).rstrip("/")
KEY = os.environ["INTERNAL_API_KEY"]
HEADERS = {"X-Internal-API-Key": KEY}

# Small public PNG
IMG_URL = (
    "https://raw.githubusercontent.com/mathiasbynens/small/master/png-transparent.png"
)


def main() -> int:
    client = httpx.Client(timeout=180.0)

    r = client.get(f"{API}/health")
    print("HEALTH", r.status_code, r.text)
    r.raise_for_status()

    r = client.get(f"{API}/queue/status", headers=HEADERS)
    print("QUEUE", r.status_code, r.text)
    r.raise_for_status()

    r = client.post(
        f"{API}/products/embedding",
        headers=HEADERS,
        data={
            "product_id": "lambda-smoke-1",
            "image_path": IMG_URL,
            "metadata": json.dumps({"title": "smoke-test", "source": "deploy"}),
        },
    )
    print("EMBED", r.status_code, r.text)
    r.raise_for_status()

    print("Waiting for worker...")
    for i in range(24):
        time.sleep(10)
        try:
            import psycopg2

            url = os.environ["DATABASE_URL"].strip().strip('"')
            conn = psycopg2.connect(url.replace("-pooler", ""))
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT product_id FROM product_embeddings WHERE product_id=%s",
                    ("lambda-smoke-1",),
                )
                row = cur.fetchone()
            conn.close()
            print(f"  poll {i+1}: neon_row={row}")
            if row:
                break
        except Exception as e:
            print(f"  poll {i+1}: {e}")
    else:
        print("Worker did not index within timeout", file=sys.stderr)
        return 1

    img_bytes = urllib.request.urlopen(IMG_URL, timeout=30).read()
    r = client.post(
        f"{API}/products/search-similar",
        headers=HEADERS,
        files={"image_file": ("smoke.png", img_bytes, "image/png")},
        data={"top_k": "5"},
    )
    print("SEARCH", r.status_code, r.text[:500])
    r.raise_for_status()
    body = r.json()
    assert body.get("count", 0) >= 1, body
    assert any(m.get("product_id") == "lambda-smoke-1" for m in body.get("matches", [])), body

    r = client.delete(f"{API}/products/embedding/lambda-smoke-1", headers=HEADERS)
    print("DELETE", r.status_code, r.text)
    r.raise_for_status()

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
