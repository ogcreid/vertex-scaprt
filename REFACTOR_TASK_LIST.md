# Refactor Task List

## Functions to Change

### 1. sitemap-orchestrator/main.py
**Function:** `sitemap_orchestrator(request)`

Remove: Request parameter `dbname`, env vars `DB_USER`, `DB_PASS`, `DB_INSTANCE`  
Add: Call fetch-sql-credentials, get all 4 values  
Add import: `google.oauth2.id_token`, `google.auth.transport.requests`

---

### 2. page-publisher/main.py
**Function:** `page_publisher(request)`

Remove: Request parameter `dbname`, env vars `DB_USER`, `DB_PASS`, `DB_INSTANCE`  
Add: Call fetch-sql-credentials once at startup  
Change: Include all 4 db values in Pub/Sub message payload

---

### 3. page-scraper-worker/main.py
**Function:** `page_scraper_worker(cloud_event)`

Remove: Env vars `DB_USER`, `DB_PASS`, `DB_INSTANCE`  
Change: Read `dbname`, `db_user`, `db_pass`, `db_instance` from Pub/Sub message  
No fetch-sql-credentials call needed (gets from message)

---

### 4. rescrape-prep/main.py
**Function:** `_build_db_dsn()`

Remove: Env vars `DB_INSTANCE`, `DB_NAME`, `DB_USER`, `DB_PASS`  
Add: Call fetch-sql-credentials, get all 4 values  
Add import: `google.oauth2.id_token`, `google.auth.transport.requests`

---

### 5. reset-pipeline-data/main.py
**Function:** `reset_pipeline_data(request)`

Remove: Request parameter `dbname`, env vars `DB_USER`, `DB_PASS`, `DB_INSTANCE`  
Add: Call fetch-sql-credentials, get all 4 values  
Add import: `google.oauth2.id_token`, `google.auth.transport.requests`

---

### 6. find-sitemaps/main.py
**Function:** `find_sitemaps_for_urls_http(request)`

Remove: Env vars `DB_INSTANCE`, `DB_NAME`, `DB_USER`, `DB_PASS`  
Add: Call fetch-sql-credentials, get all 4 values  
Add import: `google.oauth2.id_token`, `google.auth.transport.requests`

---

### 7. get-sitemap/main.py
**Function:** `find_sitemaps(request)`

No changes needed (uses external discovery module)

---

### 8. save-scraped-data-sql/main.py
**Function:** `process_scrape_entrypoint(request)`

Remove: Env var `DATABASE_URL`  
Add: Call fetch-sql-credentials, build connection string  
Add import: `google.oauth2.id_token`, `google.auth.transport.requests`

---

## YAML Changes (All Services Except #7)

**Remove from all service.yaml files:**
```yaml
- name: DB_USER
- name: DB_PASS
- name: DB_INSTANCE
- name: DB_NAME  # (rescrape-prep, find-sitemaps only)
- name: DATABASE_URL  # (save-scraped-data-sql only)
```

**No additions needed** (URL hard-coded in Python)

---

## Requirements.txt (All Services Except #7)

**Add to all:**
```
google-auth==2.23.0
```

---

## Database Change

**Update global table:**
```sql
UPDATE global SET db_name = 'zoho_rag' WHERE db_name = 'rag';
```

