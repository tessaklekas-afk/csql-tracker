import os

_sf = None


def _get_sf():
    global _sf
    if _sf is not None:
        return _sf
    username = os.getenv("SFDC_USERNAME", "")
    password = os.getenv("SFDC_PASSWORD", "")
    token = os.getenv("SFDC_SECURITY_TOKEN", "")
    domain = os.getenv("SFDC_DOMAIN", "login")
    if not (username and password):
        return None
    try:
        from simple_salesforce import Salesforce
        _sf = Salesforce(username=username, password=password,
                         security_token=token, domain=domain)
        return _sf
    except Exception as e:
        print(f"[SFDC] Connection failed: {e}")
        return None


def check_expansion_opps_bulk(account_names: list[str]) -> dict:
    """
    Given a list of account names, returns a dict mapping account_name ->
    {id, name, stage, amount, close_date} for the first open Expansion opp found.
    Accounts with no opp are not in the returned dict.
    """
    if not account_names:
        return {}
    sf = _get_sf()
    if sf is None:
        return {}
    try:
        escaped = [n.replace("'", "\\'") for n in account_names]
        names_in = ", ".join(f"'{n}'" for n in escaped)
        soql = (
            f"SELECT Account.Name, Id, Name, StageName, Amount, CloseDate "
            f"FROM Opportunity "
            f"WHERE Account.Name IN ({names_in}) "
            f"AND Type = 'Expansion' AND IsClosed = false"
        )
        result = sf.query_all(soql)
        opps = {}
        for row in result.get("records", []):
            acct_name = row.get("Account", {}).get("Name", "")
            if acct_name and acct_name not in opps:
                opps[acct_name] = {
                    "id": row["Id"],
                    "name": row["Name"],
                    "stage": row["StageName"],
                    "amount": row.get("Amount"),
                    "close_date": row.get("CloseDate"),
                }
        return opps
    except Exception as e:
        print(f"[SFDC] Query failed: {e}")
        return {}
