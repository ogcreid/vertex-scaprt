# Quick Refactor Guide: Use fetch-sql-credentials

## Overview

**Existing Service**: `fetch-sql-credentials` reads from `global` table  
**Returns**: `{user, password, db_instance, db_name}`  
**Goal**: Use ALL values from global table (including db_name)

⚠️ **Important**: Some services get `dbname` from request, others from env var `DB_NAME`  
✅ **After refactor**: ALL use `db_name` from global table (consistent!)

---

## First: Fix global table

Your global table has `db_name = 'rag'` but services use `'zoho_rag'`

**Update global table:**
```sql
UPDATE global SET db_name = 'zoho_rag' WHERE db_name = 'rag';
```

---

## page-scraper-worker Example

### 1. Add Imports (top of main.py)

```python
import google.oauth2.id_token
import google.auth.transport.requests
```

### 2. Replace Credential Code

**REMOVE (lines 42, 53-57):**
```python
dbname = job_data['dbname']  # ← Remove this, use global table instead
# ...
db_user, db_pass, db_instance = (os.environ.get(k) for k in ('DB_USER', 'DB_PASS', 'DB_INSTANCE'))
if not all([db_user, db_pass, db_instance]):
    print("Error: DB env vars must be set.")
    raise RuntimeError("Missing DB environment variables")
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

**REPLACE WITH:**
```python
# Call fetch-sql-credentials service (gets ALL db config including db_name)
credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
auth_req = google.auth.transport.requests.Request()
token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
response = requests.get(credentials_url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
creds = response.json()['data']

db_user = creds['user']
db_pass = creds['password']
db_instance = creds['db_instance']
dbname = creds['db_name']  # ✅ Use from global table, not from Pub/Sub message
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

### 3. Update service.yaml

**REMOVE:**
```yaml
- name: DB_INSTANCE
  value: vertex-ai-scraper-project:us-east4:zoho-rag
- name: DB_PASS
  value: V%p]K$n<F1(|3ggJ
- name: DB_USER
  value: postgres
```

**ADD:**
```yaml
- name: CREDENTIALS_SERVICE_URL
  value: https://fetch-sql-credentials-677825641273.us-east4.run.app
```

### 4. Update requirements.txt

**ADD:**
```
google-auth==2.23.0
```

---

## sitemap-orchestrator

**REMOVE (lines 19-27, 31):**
```python
# 2. Get dbname from request
dbname = request.args.get('dbname')
if not dbname:
    try:
        request_json = request.get_json(silent=True)
        if request_json: dbname = request_json.get('dbname')
    except Exception: pass
if not dbname:
    return ("Error: A 'dbname' must be provided.", 400)
# ...
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

**REPLACE WITH:**
```python
# Get ALL db config from fetch-sql-credentials
credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
auth_req = google.auth.transport.requests.Request()
token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
response = requests.get(credentials_url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
creds = response.json()['data']
db_user, db_pass, db_instance, dbname = creds['user'], creds['password'], creds['db_instance'], creds['db_name']
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

---

## page-publisher

**REMOVE (lines 17-23, 36):**
```python
dbname = request.args.get('dbname')
if not dbname:
    try:
        request_json = request.get_json(silent=True)
        if request_json: dbname = request_json.get('dbname')
    except Exception: pass
if not dbname: return ("Error: 'dbname' must be provided.", 400)
# ...
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

**REPLACE WITH:**
```python
# Get ALL db config from fetch-sql-credentials
credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
auth_req = google.auth.transport.requests.Request()
token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
response = requests.get(credentials_url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
creds = response.json()['data']
db_user, db_pass, db_instance, dbname = creds['user'], creds['password'], creds['db_instance'], creds['db_name']
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

---

## rescrape-prep (_build_db_dsn function)

**REMOVE:**
```python
def _build_db_dsn() -> str:
    db_instance = os.environ["DB_INSTANCE"]
    db_name     = os.environ["DB_NAME"]  # ← Remove this env var
    db_user     = os.environ["DB_USER"]
    db_pass     = os.environ["DB_PASS"]
    return f"host='/cloudsql/{db_instance}' dbname='{db_name}' user='{db_user}' password='{db_pass}'"
```

**REPLACE WITH:**
```python
def _build_db_dsn() -> str:
    credentials_url = os.environ["CREDENTIALS_SERVICE_URL"]
    auth_req = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
    response = requests.get(credentials_url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
    creds = response.json()['data']
    return f"host='/cloudsql/{creds['db_instance']}' dbname='{creds['db_name']}' user='{creds['user']}' password='{creds['password']}'"
```

---

## reset-pipeline-data

**REMOVE (lines 11-13, 23):**
```python
dbname = request.args.get('dbname')
if not dbname:
    return ("Error: A 'dbname' URL query parameter is required.", 400)
# ...
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

**REPLACE WITH:**
```python
# Get ALL db config from fetch-sql-credentials
credentials_url = os.environ.get('CREDENTIALS_SERVICE_URL')
auth_req = google.auth.transport.requests.Request()
token = google.oauth2.id_token.fetch_id_token(auth_req, credentials_url)
response = requests.get(credentials_url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
creds = response.json()['data']
db_user, db_pass, db_instance, dbname = creds['user'], creds['password'], creds['db_instance'], creds['db_name']
database_url = f"host='/cloudsql/{db_instance}' dbname='{dbname}' user='{db_user}' password='{db_pass}'"
```

---

## find-sitemaps

Same as rescrape-prep

---

## YAML Changes (All Services)

**REMOVE:**
```yaml
- name: DB_USER
  value: postgres
- name: DB_PASS
  value: V%p]K$n<F1(|3ggJ
- name: DB_INSTANCE
  value: vertex-ai-scraper-project:us-east4:zoho-rag
- name: DB_NAME          # ← Also remove this (rescrape-prep, find-sitemaps)
  value: zoho_rag
```

**ADD:**
```yaml
- name: CREDENTIALS_SERVICE_URL
  value: https://fetch-sql-credentials-677825641273.us-east4.run.app
```

---

## Summary

**Before:**
- ❌ Some services: dbname from request
- ❌ Some services: DB_NAME env var
- ❌ Inconsistent!

**After:**
- ✅ ALL services: use db_name from global table
- ✅ Consistent!
- ✅ Change database once in global table, all services update

---

## Deploy

```bash
gcloud run services replace <service-name>/service.yaml --region=us-east4
```
