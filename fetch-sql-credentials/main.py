import json
import psycopg

# ---------- Core function ----------

def fetch_global_creds():
    """
    Connects to the global database using hard-coded credentials.
    Returns the first row of the global table as a Python dict.
    """

    # Hard-coded credentials for connecting to the global database
    dsn = (
        "host='/cloudsql/vertex-ai-scraper-project:us-east4:rag' "
        "dbname='rag_global' user='postgres' password='V%p]K$n<F1(|3ggJ'"
    )

    with psycopg.connect(dsn) as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT * FROM global LIMIT 1;")  # replace with real table
        row = cur.fetchone()

    return dict(row) if row else {}

# ---------- HTTP wrapper for Cloud Run ----------

def fetch_global_creds_http(request):
    """
    HTTP Cloud Function entry point.
    """
    try:
        creds = fetch_global_creds()
        return json.dumps({"ok": True, "data": creds}), 200, {"Content-Type": "application/json"}
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}), 500, {"Content-Type": "application/json"}