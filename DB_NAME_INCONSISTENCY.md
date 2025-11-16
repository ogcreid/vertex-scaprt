# DB Name Usage

## Functions Using db_name Variable

**From request/message:**
- `sitemap_orchestrator()` - gets `dbname` from request parameter
- `reset_pipeline_data()` - gets `dbname` from request parameter
- `page_publisher()` - gets `dbname` from request parameter
- `page_scraper_worker()` - gets `dbname` from Pub/Sub message

**From environment variable:**
- `rescrape_prep_http()` - uses `DB_NAME` env var → `'zoho_rag'`
- `find_sitemaps_for_urls_http()` - uses `DB_NAME` env var → `'zoho_rag'`

- `fetch_global_creds()` - hard-coded Cloud SQL instance in DSN: `vertex-ai-scraper-project:us-east4:zoho-rag`

## Current Values

- **global table**: `db_name = 'rag'`
- **Most services use**: `'zoho_rag'`
- **Inconsistent**
