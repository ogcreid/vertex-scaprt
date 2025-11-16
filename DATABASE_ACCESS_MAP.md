# PostgreSQL Database Access Map

This document shows which functions access the PostgreSQL database, what tables/procedures they use, and what operations they perform.

---

## Summary

**8 services** access the PostgreSQL database with **33 total database operations**.

---

## Functions That Access PostgreSQL

### 1. sitemap-orchestrator/main.py

**Function**: `sitemap_orchestrator(request)`

**Database Operations**:
- **Connection**: Uses `DB_INSTANCE`, `DB_USER`, `DB_PASS` + `dbname` from request
- **Tables Accessed**:
  - `pipeline_state` (WRITE)
- **Operations**:
  1. INSERT new pipeline run record with `run_guid` and status 'starting'

**SQL Queries**:
```sql
INSERT INTO pipeline_state (run_guid, status) VALUES (%s, %s);
```

---

### 2. save-scraped-data-sql/main.py

**Functions**: 
- `process_scrape_entrypoint(request)` - HTTP entry point
- `save_scraped_data_sql(conn, ...)` - Core processing
- `DatabaseAdapter` class (UNUSED)

**Database Operations**:
- **Connection**: Uses `DATABASE_URL` environment variable
- **Tables Accessed**:
  - `pages` (READ/WRITE)
  - `blocks` (WRITE via stored procedure)
  - `page_links` (WRITE via stored procedure)
  - `chunks` (WRITE via stored procedure)
- **Operations**:
  1. Call `fn_upsert_page()` - Insert/update page metadata
  2. Call `sp_replace_blocks()` - Replace page content blocks
  3. Call `sp_replace_page_links()` - Replace page links
  4. Call `sp_replace_chunks()` - Replace text chunks

**SQL Queries**:
```sql
-- Upsert page
SELECT * FROM fn_upsert_page(%(url)s, %(title)s, %(content_hash)s, 
    %(http_status)s, %(crawled_at)s, %(updated_at)s);

-- Replace blocks
CALL sp_replace_blocks(%(page_id)s, %(blocks)s);

-- Replace links
CALL sp_replace_page_links(%(page_id)s, %(links)s);

-- Replace chunks
CALL sp_replace_chunks(%(page_id)s, %(chunks)s);
```

---

### 3. reset-pipeline-data/main.py

**Function**: `reset_pipeline_data(request)`

**Database Operations**:
- **Connection**: Uses `DB_INSTANCE`, `DB_USER`, `DB_PASS` + `dbname` from request
- **Tables Accessed**:
  - All transactional tables (via stored procedure)
- **Operations**:
  1. Call `sp_reset_pipeline_data()` - Resets all transactional data

**SQL Queries**:
```sql
CALL sp_reset_pipeline_data();
```

---

### 4. rescrape-prep/main.py

**Function**: `rescrape_prep_http(request)`

**Database Operations** (3 separate connections):
- **Connection**: Uses `DB_INSTANCE`, `DB_NAME`, `DB_USER`, `DB_PASS`
- **Tables Accessed**:
  - `sitemap_sources` (READ)
  - `sitemap_policies` (WRITE via stored procedure)
  - `urls_candidate_load` (WRITE)
  - `pages` (READ/WRITE)
- **Operations**:
  1. Call `sp_refresh_all_sitemap_policies()` - Refresh sitemap filtering policies
  2. SELECT active sitemap sources
  3. TRUNCATE `urls_candidate_load` table
  4. INSERT candidates into `urls_candidate_load`
  5. UPDATE `pages.touched_this_run` to NULL
  6. INSERT new pages from candidates
  7. UPDATE existing pages' `needs_update` flag

**SQL Queries**:
```sql
-- Refresh policies
CALL sp_refresh_all_sitemap_policies();

-- Load sources
SELECT id, index_url, policy
FROM sitemap_sources
WHERE is_active = true
ORDER BY priority DESC, id ASC;

-- Stage candidates
TRUNCATE TABLE urls_candidate_load;
INSERT INTO urls_candidate_load (url, lastmod, sitemap_id, source)
VALUES (%s, %s, %s, %s)
ON CONFLICT (url) DO NOTHING;

-- Clear prior flags
UPDATE public.pages
SET touched_this_run = NULL
WHERE touched_this_run IS TRUE;

-- Insert new pages
INSERT INTO public.pages
    (url, source, sitemap_source_id, needs_update, touched_this_run, created_at, updated_at)
SELECT c.url, COALESCE(c.source, 'sitemap') AS source, c.sitemap_id,
    TRUE, TRUE, now(), COALESCE(c.lastmod, now())
FROM public.urls_candidate_load c
LEFT JOIN public.pages p ON p.url = c.url
WHERE p.url IS NULL;

-- Flag existing pages for update
UPDATE public.pages p
SET needs_update = TRUE, touched_this_run = TRUE
FROM public.urls_candidate_load c
WHERE c.url = p.url
AND (p.updated_at IS NULL OR (c.lastmod IS NOT NULL AND c.lastmod > p.updated_at));
```

---

### 5. page-scraper-worker/main.py

**Function**: `page_scraper_worker(cloud_event)` - Pub/Sub triggered

**Database Operations** (7 separate connections):
- **Connection**: Uses `DB_INSTANCE`, `DB_USER`, `DB_PASS` + `dbname` from message
- **Tables Accessed**:
  - `urls_to_process` (READ/WRITE)
  - `pages` (READ/WRITE)
  - `app_config` (READ)
- **Operations**:
  1. UPDATE job status to 'processing'
  2. SELECT content_hash from pages (conditional)
  3. Call `fn_upsert_page()` to save scraped page
  4. SELECT language exclusions from app_config
  5. INSERT discovered links into urls_to_process
  6. UPDATE job status to 'complete' (on success)
  7. UPDATE job status to 'failed' (on error)

**SQL Queries**:
```sql
-- Mark as processing
UPDATE urls_to_process 
SET status = 'processing', worker_id = %s 
WHERE id = %s;

-- Check if content changed
SELECT content_hash FROM pages WHERE url = %s;

-- Upsert page with HTML content
SELECT * FROM fn_upsert_page(%s, %s, %s, %s, %s, %s, %s, %s);

-- Get language exclusions
SELECT config_value FROM app_config 
WHERE config_key = 'LANGUAGE_EXCLUSIONS_LIST';

-- Queue discovered links
INSERT INTO urls_to_process (run_guid, url, source, check_hash, contextual_patterns) 
VALUES (%s, %s, %s, %s, %s) 
ON CONFLICT (run_guid, url) DO NOTHING;

-- Mark complete
UPDATE urls_to_process 
SET status = 'complete', processed_at = %s 
WHERE id = %s;

-- Mark failed
UPDATE urls_to_process 
SET status = 'failed', processed_at = %s, error_message = %s 
WHERE id = %s;
```

---

### 6. page-publisher/main.py

**Function**: `page_publisher(request)`

**Database Operations** (2 connections in loop):
- **Connection**: Uses `DB_INSTANCE`, `DB_USER`, `DB_PASS` + `dbname` from request
- **Tables Accessed**:
  - `pipeline_state` (READ/WRITE)
  - `urls_to_process` (READ/WRITE)
- **Operations**:
  1. SELECT latest run_guid from pipeline_state
  2. SELECT pending URLs from urls_to_process (batches)
  3. SELECT count of active jobs (for quiescence check)
  4. UPDATE urls_to_process status to 'published'
  5. UPDATE pipeline_state status to 'complete'

**SQL Queries**:
```sql
-- Get active run
SELECT run_guid FROM pipeline_state 
ORDER BY created_at DESC LIMIT 1;

-- Get pending work
SELECT id, url, check_hash, contextual_patterns 
FROM urls_to_process 
WHERE run_guid = %s AND status = 'pending' 
LIMIT %s;

-- Check for active workers
SELECT COUNT(*) FROM urls_to_process 
WHERE run_guid = %s AND status IN ('published', 'processing');

-- Mark as published
UPDATE urls_to_process 
SET status = 'published' 
WHERE id IN (...);

-- Mark run complete
UPDATE pipeline_state 
SET status = 'complete' 
WHERE run_guid = %s;
```

---

### 7. find-sitemaps/main.py

**Function**: `find_sitemaps_for_urls_http(request)` - SKELETON CODE

**Database Operations**:
- **Connection**: Uses `DB_INSTANCE`, `DB_NAME`, `DB_USER`, `DB_PASS` (in placeholders)
- **Tables Accessed**:
  - `sitemap_policies` (WRITE via stored procedure)
  - `url_rules` (READ)
  - `sitemap_sources` (READ)
  - `site_maps_for_url` (WRITE)
- **Operations**:
  1. Call `sp_refresh_all_sitemap_policies()`
  2. SELECT base_url rules with policies
  3. INSERT discovered sitemaps into site_maps_for_url

**SQL Queries**:
```sql
-- Refresh policies
CALL sp_refresh_all_sitemap_policies();

-- Load rules
SELECT r.id as base_url_id, r.pattern, r.sitemap_source_id, s.policy
FROM url_rules r
JOIN sitemap_sources s ON s.id = r.sitemap_source_id
WHERE r.type = 'base_url';

-- Save discovered sitemaps
INSERT INTO site_maps_for_url (base_url_id, sitemap_source_id, url, type, created_at)
VALUES (%s,%s,%s,'index',now())
ON CONFLICT DO NOTHING;
```

**Note**: This is skeleton/template code with TODOs

---

### 8. fetch-sql-credentials/main.py

**Function**: `fetch_global_creds()`

**Database Operations**:
- **Connection**: Uses credentials from Google Secret Manager
  - Secrets: `global_db_user`, `global_db_pw`, `global_db_name`
  - Hard-coded instance: `vertex-ai-scraper-project:us-east4:zoho-rag`
- **Tables Accessed**:
  - `global` (READ)
- **Operations**:
  1. SELECT first row from global table

**SQL Queries**:
```sql
SELECT * FROM global LIMIT 1;
```

---

## Database Tables Access Summary

| Table | Read | Write | Used By |
|-------|------|-------|---------|
| `pipeline_state` | ✅ | ✅ | sitemap-orchestrator, page-publisher |
| `pages` | ✅ | ✅ | save-scraped-data-sql, rescrape-prep, page-scraper-worker |
| `blocks` | | ✅ | save-scraped-data-sql (via sp_replace_blocks) |
| `page_links` | | ✅ | save-scraped-data-sql (via sp_replace_page_links) |
| `chunks` | | ✅ | save-scraped-data-sql (via sp_replace_chunks) |
| `urls_to_process` | ✅ | ✅ | page-scraper-worker, page-publisher |
| `urls_candidate_load` | | ✅ | rescrape-prep |
| `sitemap_sources` | ✅ | | rescrape-prep, find-sitemaps |
| `sitemap_policies` | | ✅ | rescrape-prep, find-sitemaps (via sp_refresh) |
| `url_rules` | ✅ | | find-sitemaps |
| `site_maps_for_url` | | ✅ | find-sitemaps |
| `app_config` | ✅ | | page-scraper-worker |
| `global` | ✅ | | fetch-sql-credentials |

---

## Stored Procedures Used

| Procedure | Purpose | Called By |
|-----------|---------|-----------|
| `fn_upsert_page()` | Insert/update page metadata | save-scraped-data-sql, page-scraper-worker |
| `sp_replace_blocks()` | Replace page content blocks | save-scraped-data-sql |
| `sp_replace_page_links()` | Replace page outbound links | save-scraped-data-sql |
| `sp_replace_chunks()` | Replace text chunks | save-scraped-data-sql |
| `sp_reset_pipeline_data()` | Reset all transactional data | reset-pipeline-data |
| `sp_refresh_all_sitemap_policies()` | Refresh sitemap policies | rescrape-prep, find-sitemaps |

---

## Database Connection Patterns

### Pattern 1: Environment Variables (Most Common)
```python
db_instance = os.environ.get('DB_INSTANCE')
db_user = os.environ.get('DB_USER')
db_pass = os.environ.get('DB_PASS')
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
with psycopg.connect(database_url) as conn:
    # ...
```
**Used by**: sitemap-orchestrator, reset-pipeline-data, rescrape-prep, page-scraper-worker, page-publisher, find-sitemaps

### Pattern 2: Full Connection String
```python
DATABASE_URL = os.environ.get("DATABASE_URL")
with psycopg.connect(DATABASE_URL) as conn:
    # ...
```
**Used by**: save-scraped-data-sql

### Pattern 3: Secret Manager (Most Secure)
```python
db_user = get_secret_value("global_db_user")
db_pw = get_secret_value("global_db_pw")
dsn = f"host='/cloudsql/...' dbname='{db_name}' user='{db_user}' password='{db_pw}'"
with psycopg.connect(dsn) as conn:
    # ...
```
**Used by**: fetch-sql-credentials

---

## Database Access Statistics

- **Total Functions Accessing DB**: 8
- **Total DB Operations**: 33
- **Tables Accessed**: 13
- **Stored Procedures Used**: 6
- **Read-Only Functions**: 1 (fetch-sql-credentials)
- **Write-Heavy Functions**: 3 (save-scraped-data-sql, rescrape-prep, page-scraper-worker)

---

## Services NOT Accessing Database

These services do NOT access PostgreSQL:

1. **save-scraped-data** - Uses Google Cloud Storage only
2. **get-sitemap** - Uses external discovery module (database access unknown)
3. **filter-url** - Stateless URL filtering (no database)
4. **vertex-admin** - No Python code in repository

---

## Security Recommendations

1. ⚠️ **Hard-coded passwords**: Most services have DB passwords hard-coded in service.yaml
   - **Recommendation**: Migrate to Google Secret Manager (like fetch-sql-credentials)

2. ✅ **Connection pooling**: Currently not used
   - **Recommendation**: Consider using connection pooling for high-traffic functions

3. ✅ **Least privilege**: Each service should only have permissions for tables it accesses
   - **Recommendation**: Review database role permissions

4. ⚠️ **SQL injection**: Most queries use parameterized queries (good!)
   - **Exception**: DatabaseAdapter constructs procedure names dynamically (line 351 in save-scraped-data-sql)

