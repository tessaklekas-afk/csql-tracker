import os

import requests

def _send(payload: dict) -> bool:
    _WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
    if not _WEBHOOK:
        print(f"[SLACK stub] {payload.get('text') or 'block message'}")
        return False
    try:
        resp = requests.post(_WEBHOOK, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"[SLACK error] {e}")
        return False


def _fmt_currency(value):
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}m"
    return f"${value / 1_000:.0f}k"


def send_csql_notification(csql, magic_link: str) -> bool:
    score = csql.account_health_score
    score_str = f"{score:.0f}" if score is not None else "—"
    mau = csql.account_mau
    mau_str = f"{mau:.0f}" if mau is not None else "—"
    arr_str = _fmt_currency(csql.suggested_arr)
    renewal = csql.account_renewal_date[:10] if csql.account_renewal_date else "—"
    notes = csql.notes or "No notes provided."

    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":rocket: *New CSQL: {csql.account_name}*\nSubmitted by *{csql.submitted_by_name}*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Health Score:*\n{score_str}"},
                    {"type": "mrkdwn", "text": f"*MAU:*\n{mau_str}"},
                    {"type": "mrkdwn", "text": f"*Suggested ARR:*\n{arr_str}"},
                    {"type": "mrkdwn", "text": f"*Renewal Date:*\n{renewal}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Notes:*\n{notes}"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Review CSQL \u2192"},
                        "url": magic_link,
                        "style": "primary",
                    }
                ],
            },
        ]
    }
    return _send(payload)
