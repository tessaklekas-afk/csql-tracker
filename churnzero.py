import os
from urllib.parse import quote

import requests

def _headers():
    auth = os.getenv("CHURNZERO_BASIC_AUTH", "")
    return {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    }


def _rest_base():
    base = os.getenv("CHURNZERO_BASE_URL", "https://trmlabs.us2app.churnzero.net").rstrip("/")
    return f"{base}/public/v1"


def _get(endpoint, filter_str=None, top=50):
    params = []
    if filter_str:
        params.append(f"$filter={quote(filter_str)}")
    if top:
        params.append(f"$top={top}")
    qs = "?" + "&".join(params) if params else ""
    url = f"{_rest_base()}{endpoint}{qs}"
    resp = requests.get(url, headers=_headers(), timeout=15)
    if not resp.ok:
        raise RuntimeError(f"ChurnZero API error {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def get_high_health_accounts(min_score=70, top=50):
    """Return active accounts with health score >= min_score, sorted by score desc."""
    data = _get(
        "/Account",
        filter_str=f"PrimaryChurnScoreValue ge {min_score} and IsActive eq true",
        top=top,
    )
    accounts = data.get("value", [])
    accounts.sort(key=lambda a: a.get("PrimaryChurnScoreValue") or 0, reverse=True)
    return accounts


def search_accounts_by_name(name, top=15):
    """Search accounts by name (partial match). Returns list."""
    safe_name = name.replace("'", "''")
    data = _get(
        "/Account",
        filter_str=f"contains(Name,'{safe_name}') and IsActive eq true",
        top=top,
    )
    return data.get("value", [])


def get_account_by_external_id(external_id):
    """Fetch a single account by ExternalId. Returns account dict or None."""
    safe_id = external_id.replace("'", "''")
    data = _get(f"/Account(AccountExternalId='{quote(safe_id)}')")
    values = data.get("value", [])
    return values[0] if values else None


def get_contacts_for_account(account_cz_id, top=100):
    """Fetch contacts for an account by its internal ChurnZero ID."""
    data = _get("/Contact", filter_str=f"AccountId eq {account_cz_id}", top=top)
    return data.get("value", [])
