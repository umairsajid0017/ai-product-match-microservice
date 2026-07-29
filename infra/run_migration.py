import os
import pathlib
import sys

import psycopg2

url = (os.environ.get("DATABASE_URL") or "").strip().strip('"').strip("'")
if not url:
    print("DATABASE_URL missing", file=sys.stderr)
    sys.exit(1)

direct = url.replace("-pooler", "")
sql_path = pathlib.Path(__file__).resolve().parents[1] / "sql" / "001_product_embeddings.sql"
sql = sql_path.read_text(encoding="utf-8")

for attempt, u in enumerate([direct, url], 1):
    try:
        print(f"Connecting attempt {attempt}...")
        conn = psycopg2.connect(u)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("SELECT extname FROM pg_extension WHERE extname='vector'")
            print("extension:", cur.fetchone())
            cur.execute("SELECT to_regclass('public.product_embeddings')")
            print("table:", cur.fetchone())
        conn.close()
        print("Migration OK")
        sys.exit(0)
    except Exception as e:
        print(f"Attempt {attempt} failed: {type(e).__name__}: {e}")

sys.exit(1)
