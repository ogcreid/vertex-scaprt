# Environment Variables to Delete - Quick Reference

## ✅ SAFE TO DELETE NOW (Confirmed Unused)

### 1. sitemap-orchestrator/service.yaml
Delete these 4 variables:
```yaml
- name: DATA_BUCKET
  value: scraper-data-bucket-vertex-ai-scraper-project
  
- name: CONFIG_BUCKET
  value: scraper-config-bucket-vertex-ai-scraper-project
  
- name: SITEMAP_COMPARATOR_URL
  value: https://sitemap-comparator-677825641273.us-east4.run.app
  
- name: PRUNER_URL
  value: https://prune-sitemap-677825641273.us-east4.run.app
```

### 2. save-scraped-data-sql/service.yaml
Delete this 1 variable:
```yaml
- name: LOG_LEVEL
  value: INFO
```

## ⚠️ INVESTIGATE FIRST (Potentially Unused)

### 3. get-sitemap/service.yaml
**All 6 variables potentially unused** (depends on missing `discovery` module):
```yaml
- name: DATA_BUCKET
  value: scraper-data-bucket-vertex-ai-scraper-project
  
- name: CONFIG_BUCKET
  value: scraper-config-bucket-vertex-ai-scraper-project
  
- name: DB_INSTANCE
  value: vertex-ai-scraper-project:us-east4:zoho-rag
  
- name: DB_PASS
  value: V%p]K$n<F1(|3ggJ
  
- name: DB_USER
  value: postgres
  
- name: FILTER_URL_ENDPOINT
  value: https://filter-url-677825641273.us-east4.run.app
```

**Action**: Check if the external `discovery` module uses these variables. If not, delete all 6.

## 🔧 FIX THIS BUG

### 4. vertex-admin/service.yaml
Fix typo (trailing space in variable name):
```yaml
# WRONG (has trailing space):
- name: 'ALLOWED_DBS '
  value: zoho_rag

# CORRECT (no trailing space):
- name: 'ALLOWED_DBS'
  value: zoho_rag
```

---

## Quick Summary

| Service | Variables to Delete | Count |
|---------|-------------------|-------|
| sitemap-orchestrator | DATA_BUCKET, CONFIG_BUCKET, SITEMAP_COMPARATOR_URL, PRUNER_URL | 4 |
| save-scraped-data-sql | LOG_LEVEL | 1 |
| get-sitemap | All 6 variables (pending investigation) | 6 |
| **TOTAL** | **5-11 variables** | **5-11** |

---

## Commands to Delete Variables

### Option 1: Manual Deletion
Edit each service.yaml file and remove the specified variables from the `env:` section.

### Option 2: Using gcloud CLI
You can also update via gcloud command:

```bash
# Example for sitemap-orchestrator
gcloud run services update sitemap-orchestrator \
  --region=us-east4 \
  --remove-env-vars="DATA_BUCKET,CONFIG_BUCKET,SITEMAP_COMPARATOR_URL,PRUNER_URL"

# Example for save-scraped-data-sql
gcloud run services update save-scraped-data-sql \
  --region=us-east4 \
  --remove-env-vars="LOG_LEVEL"
```

---

## Before You Delete

✅ **Checklist**:
1. [ ] Backup current service.yaml files
2. [ ] Verify services are working correctly before changes
3. [ ] Delete variables one service at a time
4. [ ] Test service after each deletion
5. [ ] Monitor logs for any errors about missing environment variables

⚠️ **Warning**: If you see errors after deletion like:
- `KeyError: 'VARIABLE_NAME'`
- `Environment variable VARIABLE_NAME not found`

Then the variable WAS being used. Restore it immediately.

