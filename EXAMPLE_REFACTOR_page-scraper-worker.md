# Example Refactor: page-scraper-worker

## Complete Before/After Comparison

---

## BEFORE (Current Code)

### File: `page-scraper-worker/main.py`

```python
import os
import uuid
import psycopg
import requests
import json
import base64
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone
import functions_framework
import hashlib

# --- Helper Functions ---
def extract_metadata(soup):
    """Extracts title and last modified timestamp from HTML soup."""
    title = (soup.title.string or "").strip() if soup.title else ""
    modified_time_tag = soup.find('meta', property='article:modified_time')
    if modified_time_tag and modified_time_tag.get('content'):
        try:
            return title, datetime.fromisoformat(modified_time_tag['content'].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return title, None

def get_base_domain(url: str):
    """Gets the base domain (e.g., zoho.com) from a URL."""
    hostname = urlparse(url).hostname
    if not hostname: return ""
    parts = hostname.split('.')
    return ".".join(parts[-2:]) if len(parts) > 2 else hostname

# --- Main Cloud Function ---
@functions_framework.cloud_event
def page_scraper_worker(cloud_event):
    # 1. Get Job Details from Pub/Sub Message
    try:
        payload_str = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
        job_data = json.loads(payload_str)
        url_id = job_data['url_id']
        url = job_data['url']
        run_guid = job_data['run_guid']
        dbname = job_data['dbname']
        check_hash = job_data['check_hash']
        patterns_str = job_data['contextual_patterns']
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error: Could not decode Pub/Sub message. Malformed payload. Error: {e}")
        return

    worker_id = str(uuid.uuid4())
    print(f"Worker {worker_id} started for URL ID {url_id}: {url}")

    # ❌ OLD: Get DB Config from environment variables
    db_user, db_pass, db_instance = (os.environ.get(k) for k in ('DB_USER', 'DB_PASS', 'DB_INSTANCE'))
    if not all([db_user, db_pass, db_instance]):
        print("Error: DB env vars must be set.")
        raise RuntimeError("Missing DB environment variables")
    database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"

    # ... rest of code continues ...
```

### File: `page-scraper-worker/service.yaml` (lines 44-50)

```yaml
      - env:
        - name: DB_INSTANCE
          value: vertex-ai-scraper-project:us-east4:zoho-rag
        - name: DB_PASS
          value: V%p]K$n<F1(|3ggJ      # ❌ Password visible!
        - name: DB_USER
          value: postgres
```

### File: `page-scraper-worker/requirements.txt`

```
functions-framework==3.*
psycopg[binary]==3.*
beautifulsoup4==4.*
lxml==4.*
requests==2.*
```

---

## AFTER (Refactored Code)

### File: `page-scraper-worker/main.py`

```python
import os
import uuid
import psycopg
import requests
import json
import base64
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone
import functions_framework
import hashlib
import google.oauth2.id_token          # ✅ NEW
import google.auth.transport.requests  # ✅ NEW

# --- Helper Functions ---
def extract_metadata(soup):
    """Extracts title and last modified timestamp from HTML soup."""
    title = (soup.title.string or "").strip() if soup.title else ""
    modified_time_tag = soup.find('meta', property='article:modified_time')
    if modified_time_tag and modified_time_tag.get('content'):
        try:
            return title, datetime.fromisoformat(modified_time_tag['content'].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return title, None

def get_base_domain(url: str):
    """Gets the base domain (e.g., zoho.com) from a URL."""
    hostname = urlparse(url).hostname
    if not hostname: return ""
    parts = hostname.split('.')
    return ".".join(parts[-2:]) if len(parts) > 2 else hostname

# ✅ NEW: Fetch credentials from centralized service
def get_db_credentials():
    """
    Fetches database credentials from the centralized credentials service.
    
    Returns:
        dict: Contains 'user', 'password', 'db_instance', 'db_name'
    
    Raises:
        RuntimeError: If credentials cannot be fetched
    """
    credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
    if not credentials_url:
        raise RuntimeError("CREDENTIALS_SERVICE_URL environment variable not set")
    
    try:
        # Authenticate service-to-service call
        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
        headers = {'Authorization': f'Bearer {token}'}
        
        # Call credentials service
        response = requests.get(credentials_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse response
        result = response.json()
        if not result.get('ok'):
            raise RuntimeError(f"Credentials service error: {result.get('error')}")
        
        return result['data']
    
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch credentials: {e}")

# --- Main Cloud Function ---
@functions_framework.cloud_event
def page_scraper_worker(cloud_event):
    # 1. Get Job Details from Pub/Sub Message
    try:
        payload_str = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
        job_data = json.loads(payload_str)
        url_id = job_data['url_id']
        url = job_data['url']
        run_guid = job_data['run_guid']
        dbname = job_data['dbname']
        check_hash = job_data['check_hash']
        patterns_str = job_data['contextual_patterns']
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error: Could not decode Pub/Sub message. Malformed payload. Error: {e}")
        return

    worker_id = str(uuid.uuid4())
    print(f"Worker {worker_id} started for URL ID {url_id}: {url}")

    # ✅ NEW: Get DB Config from centralized credentials service
    try:
        creds = get_db_credentials()
        db_user = creds['user']
        db_pass = creds['password']
        db_instance = creds['db_instance']
        print(f"Successfully fetched credentials for user: {db_user}")
    except Exception as e:
        print(f"Error fetching database credentials: {e}")
        raise RuntimeError("Failed to fetch database credentials")
    
    database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"

    # ... rest of code continues unchanged ...
```

### File: `page-scraper-worker/service.yaml` (lines 44-48)

```yaml
      - env:
        - name: CREDENTIALS_SERVICE_URL
          value: https://fetch-sql-credentials-677825641273.us-east4.run.app
        # ✅ DB_INSTANCE, DB_PASS, DB_USER removed - no more hard-coded credentials!
```

### File: `page-scraper-worker/requirements.txt`

```
functions-framework==3.*
psycopg[binary]==3.*
beautifulsoup4==4.*
lxml==4.*
requests==2.*
google-auth==2.23.0        # ✅ NEW: For service-to-service auth
```

---

## Summary of Changes

### 1. Code Changes (`main.py`)

| Change | Lines | Description |
|--------|-------|-------------|
| ➕ Add imports | 12-13 | Import `google.oauth2.id_token` and `google.auth.transport.requests` |
| ➕ New function | 33-63 | Add `get_db_credentials()` function |
| ✏️ Replace code | 85-91 | Replace env var fetching with credential service call |
| ➕ Add logging | 90 | Add success log for credential fetch |
| ➕ Add error handling | 91-93 | Better error handling for credential failures |

### 2. Environment Variable Changes (`service.yaml`)

| Action | Variable | Old Value | New Value |
|--------|----------|-----------|-----------|
| ➕ ADD | `CREDENTIALS_SERVICE_URL` | - | `https://fetch-sql-credentials-677825641273.us-east4.run.app` |
| ❌ REMOVE | `DB_USER` | `postgres` | (deleted) |
| ❌ REMOVE | `DB_PASS` | `V%p]K$n<F1(|3ggJ` | (deleted) |
| ❌ REMOVE | `DB_INSTANCE` | `vertex-ai-scraper-project:us-east4:zoho-rag` | (deleted) |

### 3. Dependency Changes (`requirements.txt`)

| Action | Package | Version |
|--------|---------|---------|
| ➕ ADD | `google-auth` | `2.23.0` |

---

## Deployment Steps

### Step 1: Test Credentials Service

```bash
# Test that the credentials service is working
curl https://fetch-sql-credentials-677825641273.us-east4.run.app

# Expected output:
# {"ok": true, "data": {"db_name": "rag", "password": "V%p]K$n<F1(|3ggJ", "user": "postgres", "db_instance": "vertex-ai-scraper-project:us-east4:rag"}}
```

### Step 2: Update Local Files

```bash
cd page-scraper-worker

# Backup current version
cp main.py main.py.backup
cp service.yaml service.yaml.backup
cp requirements.txt requirements.txt.backup

# Apply changes
# (Edit files with changes shown above)
```

### Step 3: Deploy

```bash
# Deploy the updated service
gcloud run services replace page-scraper-worker/service.yaml --region=us-east4

# Or if using directory deployment:
gcloud run deploy page-scraper-worker \
  --source=./page-scraper-worker \
  --region=us-east4 \
  --platform=managed
```

### Step 4: Test

```bash
# Monitor logs
gcloud run services logs read page-scraper-worker --region=us-east4 --follow

# Look for this log line:
# "Successfully fetched credentials for user: postgres"
```

### Step 5: Verify

Trigger a test scrape and verify:
- ✅ No "Missing DB environment variables" errors
- ✅ "Successfully fetched credentials" appears in logs
- ✅ Database connections work correctly
- ✅ Scraping completes successfully

---

## Rollback (If Needed)

If something goes wrong:

```bash
cd page-scraper-worker

# Restore backups
cp main.py.backup main.py
cp service.yaml.backup service.yaml
cp requirements.txt.backup requirements.txt

# Redeploy
gcloud run services replace page-scraper-worker/service.yaml --region=us-east4
```

---

## Security Benefits

### Before:
```
❌ Password visible in service.yaml
❌ Password in Git repository
❌ Password in Cloud Console UI
❌ Password in deployment logs
❌ Anyone with repo access has password
❌ Hard to rotate credentials
```

### After:
```
✅ Password only in Secret Manager
✅ No passwords in Git
✅ No passwords in Cloud Console
✅ No passwords in logs
✅ IAM controls who can read secrets
✅ Easy credential rotation
✅ Audit trail of secret access
```

---

## Bonus: Add Caching (Optional)

To reduce calls to the credentials service, add caching:

```python
from functools import lru_cache
from datetime import datetime, timedelta

# Cache credentials for 1 hour
_credentials_cache = None
_credentials_timestamp = None
CACHE_TTL = timedelta(hours=1)

def get_db_credentials():
    """Fetches database credentials with caching."""
    global _credentials_cache, _credentials_timestamp
    
    # Return cached credentials if still valid
    if _credentials_cache and _credentials_timestamp:
        if datetime.now() - _credentials_timestamp < CACHE_TTL:
            print("Using cached credentials")
            return _credentials_cache
    
    # Fetch fresh credentials
    credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
    if not credentials_url:
        raise RuntimeError("CREDENTIALS_SERVICE_URL not set")
    
    try:
        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
        headers = {'Authorization': f'Bearer {token}'}
        
        response = requests.get(credentials_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if not result.get('ok'):
            raise RuntimeError(f"Credentials error: {result.get('error')}")
        
        # Cache the credentials
        _credentials_cache = result['data']
        _credentials_timestamp = datetime.now()
        print("Fetched and cached new credentials")
        
        return _credentials_cache
    
    except requests.exceptions.RequestException as e:
        # If fetch fails but we have cached creds, use them
        if _credentials_cache:
            print(f"Warning: Failed to fetch fresh credentials ({e}), using cached")
            return _credentials_cache
        raise RuntimeError(f"Failed to fetch credentials: {e}")
```

---

## Estimated Time

- **Code changes**: 15 minutes
- **Testing locally**: 10 minutes  
- **Deployment**: 5 minutes
- **Verification**: 10 minutes

**Total: ~40 minutes per service**

---

## Next Services to Convert

Once `page-scraper-worker` is successful, convert in this order:

1. ✅ **page-scraper-worker** (done - example above)
2. ⏭️ **page-publisher** (very similar changes)
3. ⏭️ **sitemap-orchestrator** (similar changes)
4. ⏭️ **rescrape-prep** (similar changes)
5. ⏭️ **reset-pipeline-data** (similar changes)

All follow the same pattern - should take ~40 minutes each!

