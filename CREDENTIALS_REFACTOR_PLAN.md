# Centralize Database Credentials - Refactor Plan

## Goal
Replace hard-coded environment variables with centralized credential fetching via `fetch-sql-credentials` service.

## Benefits
1. ✅ **Security**: Credentials stored in Google Secret Manager (not in YAML files)
2. ✅ **Centralized**: One place to update credentials
3. ✅ **Audit Trail**: Secret Manager tracks all credential access
4. ✅ **Rotation**: Easy to rotate credentials without redeploying services
5. ✅ **No Hard-coding**: Remove passwords from service.yaml files

---

## Example: page-scraper-worker

### BEFORE (Current Implementation)

**Environment Variables** (from `page-scraper-worker/service.yaml`):
```yaml
env:
  - name: DB_INSTANCE
    value: vertex-ai-scraper-project:us-east4:zoho-rag
  - name: DB_PASS
    value: V%p]K$n<F1(|3ggJ
  - name: DB_USER
    value: postgres
```

**Code** (from `page-scraper-worker/main.py` lines 53-57):
```python
# 2. Get DB Config
db_user, db_pass, db_instance = (os.environ.get(k) for k in ('DB_USER', 'DB_PASS', 'DB_INSTANCE'))
if not all([db_user, db_pass, db_instance]):
    print("Error: DB env vars must be set.")
    raise RuntimeError("Missing DB environment variables")
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

---

### AFTER (New Implementation)

**Environment Variables** (from `page-scraper-worker/service.yaml`):
```yaml
env:
  - name: CREDENTIALS_SERVICE_URL
    value: https://fetch-sql-credentials-677825641273.us-east4.run.app
  # DB_INSTANCE, DB_PASS, DB_USER are REMOVED
```

**New Code** (for `page-scraper-worker/main.py`):

```python
import requests
import google.oauth2.id_token
import google.auth.transport.requests

def get_db_credentials():
    """
    Fetches database credentials from the centralized credentials service.
    Returns dict with: db_name, password, user, db_instance
    """
    credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
    if not credentials_url:
        raise RuntimeError("CREDENTIALS_SERVICE_URL environment variable not set")
    
    # Get authentication token for service-to-service calls
    auth_req = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
    
    # Call the credentials service
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(credentials_url, headers=headers, timeout=10)
    response.raise_for_status()
    
    # Parse response
    result = response.json()
    if not result.get('ok'):
        raise RuntimeError(f"Credentials service error: {result.get('error')}")
    
    return result['data']

# In the main function, replace lines 53-57 with:
def page_scraper_worker(cloud_event):
    # ... existing code ...
    
    # 2. Get DB Config from centralized service
    try:
        creds = get_db_credentials()
        db_user = creds['user']
        db_pass = creds['password']
        db_instance = creds['db_instance']
    except Exception as e:
        print(f"Error fetching credentials: {e}")
        raise RuntimeError("Failed to fetch database credentials")
    
    database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
    
    # ... rest of the code stays the same ...
```

---

## Step-by-Step Implementation Guide

### Step 1: Update `fetch-sql-credentials` Service

**Ensure the service is properly deployed and accessible:**

```bash
# Test the service
curl https://fetch-sql-credentials-677825641273.us-east4.run.app

# Should return:
# {"ok": true, "data": {"db_name": "rag", "password": "...", "user": "postgres", "db_instance": "..."}}
```

### Step 2: Update Target Service Code

For `page-scraper-worker/main.py`:

1. **Add import statements** at the top:
```python
import google.oauth2.id_token
import google.auth.transport.requests
```

2. **Add helper function** (after imports):
```python
def get_db_credentials():
    """Fetches database credentials from centralized service."""
    credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
    if not credentials_url:
        raise RuntimeError("CREDENTIALS_SERVICE_URL not set")
    
    auth_req = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
    headers = {'Authorization': f'Bearer {token}'}
    
    response = requests.get(credentials_url, headers=headers, timeout=10)
    response.raise_for_status()
    
    result = response.json()
    if not result.get('ok'):
        raise RuntimeError(f"Credentials error: {result.get('error')}")
    
    return result['data']
```

3. **Replace credential fetching code** in `page_scraper_worker()`:

**OLD:**
```python
db_user, db_pass, db_instance = (os.environ.get(k) for k in ('DB_USER', 'DB_PASS', 'DB_INSTANCE'))
if not all([db_user, db_pass, db_instance]):
    print("Error: DB env vars must be set.")
    raise RuntimeError("Missing DB environment variables")
```

**NEW:**
```python
try:
    creds = get_db_credentials()
    db_user = creds['user']
    db_pass = creds['password']
    db_instance = creds['db_instance']
except Exception as e:
    print(f"Error fetching credentials: {e}")
    raise RuntimeError("Failed to fetch database credentials")
```

### Step 3: Update service.yaml

**Edit `page-scraper-worker/service.yaml`:**

**REMOVE these lines:**
```yaml
- name: DB_INSTANCE
  value: vertex-ai-scraper-project:us-east4:zoho-rag
- name: DB_PASS
  value: V%p]K$n<F1(|3ggJ
- name: DB_USER
  value: postgres
```

**ADD this line:**
```yaml
- name: CREDENTIALS_SERVICE_URL
  value: https://fetch-sql-credentials-677825641273.us-east4.run.app
```

### Step 4: Update requirements.txt

**Add to `page-scraper-worker/requirements.txt`:**
```
google-auth==2.23.0
```

### Step 5: Deploy and Test

```bash
# Deploy the updated service
gcloud run services replace page-scraper-worker/service.yaml --region=us-east4

# Test the service
# Trigger a scrape job and monitor logs
gcloud run services logs read page-scraper-worker --region=us-east4 --limit=50
```

---

## Services to Refactor (Priority Order)

### Priority 1: Active Services (Convert First)
These are actively used and would benefit most:

1. **✅ page-scraper-worker** (example above)
   - Current env vars: `DB_USER`, `DB_PASS`, `DB_INSTANCE`
   - Impact: High (worker processes all scraping)

2. **✅ page-publisher**
   - Current env vars: `DB_USER`, `DB_PASS`, `DB_INSTANCE`
   - Impact: High (publishes jobs to workers)

3. **✅ sitemap-orchestrator**
   - Current env vars: `DB_USER`, `DB_PASS`, `DB_INSTANCE`
   - Impact: Medium (orchestrates pipeline)

4. **✅ rescrape-prep**
   - Current env vars: `DB_USER`, `DB_PASS`, `DB_INSTANCE`, `DB_NAME`
   - Impact: Medium (prepares scraping queue)

### Priority 2: Admin/Utility Services

5. **✅ reset-pipeline-data**
   - Current env vars: `DB_USER`, `DB_PASS`, `DB_INSTANCE`
   - Impact: Low (admin tool)

6. **✅ find-sitemaps**
   - Current env vars: `DB_USER`, `DB_PASS`, `DB_INSTANCE`, `DB_NAME`
   - Impact: Low (skeleton code)

### Priority 3: Special Cases

7. **⚠️ save-scraped-data-sql**
   - Current env var: `DATABASE_URL` (full connection string)
   - Impact: Unknown (possibly unused)
   - Note: Uses different format - needs special handling

8. **⚠️ get-sitemap**
   - Current env vars: `DB_USER`, `DB_PASS`, `DB_INSTANCE`
   - Impact: Unknown (missing discovery module)
   - Note: May need credentials in external module

### Services That Don't Need Changes

- ❌ **save-scraped-data** - Uses Cloud Storage, no DB
- ❌ **filter-url** - Stateless, no DB
- ❌ **fetch-sql-credentials** - Already uses Secret Manager

---

## Special Case: save-scraped-data-sql

This service uses a different format (`DATABASE_URL` instead of individual vars).

**Current:**
```yaml
env:
  - name: DATABASE_URL
    value: postgresql://user:pass@host:5432/zoho_rag
```

**After:**
```python
def get_database_url():
    """Build DATABASE_URL from credentials service."""
    creds = get_db_credentials()
    # Note: This service uses direct PostgreSQL connection, not Cloud SQL proxy
    # You may need to adjust this based on your actual connection method
    return f"postgresql://{creds['user']}:{creds['password']}@/cloudsql/{creds['db_instance']}/{creds['db_name']}"

# In code:
DATABASE_URL = get_database_url()
```

---

## Security Improvements Summary

### Before Refactor:
```
service.yaml files (8 files) → Hard-coded passwords visible in:
  - Git repository
  - Cloud Console
  - Deployment logs
  - Anyone with repo access
```

### After Refactor:
```
Secret Manager → fetch-sql-credentials → Individual services
  ✅ Passwords never in code
  ✅ Centralized management
  ✅ Audit logging
  ✅ Easy rotation
  ✅ IAM-controlled access
```

---

## Environment Variables to Remove (After Refactor)

Once all services are converted, you can delete these from service.yaml files:

| Service | Variables to REMOVE | Replace With |
|---------|-------------------|--------------|
| sitemap-orchestrator | `DB_USER`, `DB_PASS`, `DB_INSTANCE` | `CREDENTIALS_SERVICE_URL` |
| page-scraper-worker | `DB_USER`, `DB_PASS`, `DB_INSTANCE` | `CREDENTIALS_SERVICE_URL` |
| page-publisher | `DB_USER`, `DB_PASS`, `DB_INSTANCE` | `CREDENTIALS_SERVICE_URL` |
| rescrape-prep | `DB_USER`, `DB_PASS`, `DB_INSTANCE`, `DB_NAME` | `CREDENTIALS_SERVICE_URL` |
| reset-pipeline-data | `DB_USER`, `DB_PASS`, `DB_INSTANCE` | `CREDENTIALS_SERVICE_URL` |
| find-sitemaps | `DB_USER`, `DB_PASS`, `DB_INSTANCE`, `DB_NAME` | `CREDENTIALS_SERVICE_URL` |
| get-sitemap | `DB_USER`, `DB_PASS`, `DB_INSTANCE` | `CREDENTIALS_SERVICE_URL` |
| save-scraped-data-sql | `DATABASE_URL` | `CREDENTIALS_SERVICE_URL` |

**Total: 22 environment variables removed, replaced with 1 URL!**

---

## Testing Checklist

For each service you refactor:

- [ ] Code changes applied
- [ ] service.yaml updated (removed old vars, added CREDENTIALS_SERVICE_URL)
- [ ] requirements.txt updated (added google-auth)
- [ ] Service deployed successfully
- [ ] Logs show successful credential fetch
- [ ] Service functions correctly
- [ ] No "missing environment variable" errors
- [ ] Credentials are correct

---

## Rollback Plan

If something goes wrong, you can quickly rollback:

1. **Revert service.yaml** to add back old environment variables
2. **Revert code** to use `os.environ.get()` instead of `get_db_credentials()`
3. **Redeploy** the service

Keep a backup of all original service.yaml files before starting!

---

## Implementation Timeline

### Week 1: Setup & Testing
- [ ] Test `fetch-sql-credentials` service thoroughly
- [ ] Create `get_db_credentials()` helper as reusable module
- [ ] Convert **page-scraper-worker** (test in isolation)

### Week 2: Core Services
- [ ] Convert **page-publisher**
- [ ] Convert **sitemap-orchestrator**
- [ ] Test complete pipeline end-to-end

### Week 3: Remaining Services
- [ ] Convert **rescrape-prep**
- [ ] Convert **reset-pipeline-data**
- [ ] Convert **find-sitemaps**

### Week 4: Special Cases & Cleanup
- [ ] Handle **save-scraped-data-sql** special case
- [ ] Handle **get-sitemap** (if needed)
- [ ] Remove all old environment variables
- [ ] Update documentation

---

## Additional Improvements

### Consider Creating a Shared Library

Create `common/db_credentials.py`:

```python
"""Shared module for fetching database credentials."""
import os
import requests
import google.oauth2.id_token
import google.auth.transport.requests

def get_db_credentials():
    """
    Fetches database credentials from centralized service.
    
    Returns:
        dict: {
            'db_name': str,
            'password': str,
            'user': str,
            'db_instance': str
        }
    
    Raises:
        RuntimeError: If credentials cannot be fetched
    """
    credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
    if not credentials_url:
        raise RuntimeError("CREDENTIALS_SERVICE_URL environment variable not set")
    
    try:
        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
        headers = {'Authorization': f'Bearer {token}'}
        
        response = requests.get(credentials_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if not result.get('ok'):
            raise RuntimeError(f"Credentials service error: {result.get('error')}")
        
        return result['data']
    
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch credentials: {e}")

def build_database_url(dbname=None):
    """
    Builds a database connection string using fetched credentials.
    
    Args:
        dbname: Optional database name override
    
    Returns:
        str: Database connection URL
    """
    creds = get_db_credentials()
    db = dbname or creds.get('db_name', 'postgres')
    return f"host='/cloudsql/{creds['db_instance']}' dbname='{db}' user='{creds['user']}' password='{creds['password']}'"
```

Then each service just does:
```python
from common.db_credentials import build_database_url

database_url = build_database_url(dbname='zoho_rag')
```

---

## Cost Impact

**Before:** 22 environment variables across 8 services
**After:** 8 HTTP calls to `fetch-sql-credentials` (one per service startup)

**Cost:** Negligible (~$0.000001 per call) - saves money by improving security!

---

## Questions?

- **Q: What if `fetch-sql-credentials` is down?**
  - A: Services will fail to start - add retry logic with exponential backoff

- **Q: Performance impact?**
  - A: Minimal - credentials fetched once at startup, cached in memory

- **Q: Can we cache credentials?**
  - A: Yes, but implement TTL (e.g., 1 hour) to allow rotation

- **Q: What about local development?**
  - A: Set `CREDENTIALS_SERVICE_URL=http://localhost:8080` and run service locally

