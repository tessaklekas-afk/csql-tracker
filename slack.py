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
    score_str = f"{csql.account_health_score:.0f}" if csql.account_health_score is not None else "—"
    mau_str = f"{csql.account_mau:.0f}" if csql.account_mau is not None else "—"
    renewal = csql.account_renewal_date[:10] if csql.account_renewal_date else "—"

    # Build header line
    header = f":rocket: *New CSQL: {csql.account_name}*\nSubmitted by *{csql.submitted_by_name}*"
    if csql.expansion_reason:
        header += f"  ·  {csql.expansion_reason}"

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": header},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Health Score:*\n{score_str}"},
                {"type": "mrkdwn", "text": f"*MAU:*\n{mau_str}"},
                {"type": "mrkdwn", "text": f"*Contract Value:*\n{_fmt_currency(csql.account_contract_value)}"},
                {"type": "mrkdwn", "text": f"*Next Contract:*\n{_fmt_currency(csql.account_next_renewal_amount)}"},
                {"type": "mrkdwn", "text": f"*Renewal Date:*\n{renewal}"},
                {"type": "mrkdwn", "text": f"*Suggested ARR:*\n{_fmt_currency(csql.suggested_arr)}"},
            ],
        },
    ]

    # Expansion signal
    if csql.expansion_signal:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Expansion Signal:*\n{csql.expansion_signal}"},
        })

    # Contact + CSM
    contact_parts = []
    if csql.contact_name:
        contact_parts.append(f"*Key Contact:* {csql.contact_name}")
    if csql.csm_name:
        contact_parts.append(f"*Deployment Strategist:* {csql.csm_name}")
    if csql.primary_product_opportunity:
        contact_parts.append(f"*Primary Product:* {csql.primary_product_opportunity}")
    if contact_parts:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "  ·  ".join(contact_parts)},
        })

    # Notes
    if csql.notes:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Notes from CSM:*\n{csql.notes}"},
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Review CSQL \u2192"},
                "url": magic_link,
                "style": "primary",
            }
        ],
    })

    return _send({"blocks": blocks})
