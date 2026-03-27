import secrets
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class CSQL(db.Model):
    __tablename__ = "csqls"

    id = db.Column(db.Integer, primary_key=True)
    magic_token = db.Column(
        db.String(64), unique=True, default=lambda: secrets.token_urlsafe(32)
    )

    # ChurnZero snapshot captured at submission time
    account_external_id = db.Column(db.String(255), nullable=False)
    account_name = db.Column(db.String(255), nullable=False)
    account_health_score = db.Column(db.Float)
    account_mau = db.Column(db.Float)
    account_contract_value = db.Column(db.Float)
    account_renewal_date = db.Column(db.String(50))
    account_next_renewal_amount = db.Column(db.Float)
    account_api_utilization = db.Column(db.Float)       # % used this contract year
    account_contact_count = db.Column(db.Integer)

    # Submission fields
    submitted_by_name = db.Column(db.String(255), nullable=False)
    submitted_by_email = db.Column(db.String(255))
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text)
    suggested_arr = db.Column(db.Float)
    suggested_close_date = db.Column(db.Date)
    ad_email = db.Column(db.String(255))

    # CSQL signal details
    expansion_reason = db.Column(db.String(100))
    expansion_signal = db.Column(db.Text)
    expansion_date = db.Column(db.Date)
    primary_product_opportunity = db.Column(db.String(255))
    contact_external_id = db.Column(db.String(255))
    contact_name = db.Column(db.String(255))
    csm_name = db.Column(db.String(255))
    csm_email = db.Column(db.String(255))

    # Status: pending | accepted | declined
    status = db.Column(db.String(20), nullable=False, default="pending")

    # AD response
    ad_response_notes = db.Column(db.Text)
    pipeline_created = db.Column(db.Boolean, default=False)
    pipeline_accepted_arr = db.Column(db.Float)
    pipeline_accepted_close_date = db.Column(db.Date)
    expansion_opportunity_exists = db.Column(db.Boolean, default=False)
    expansion_opportunity_id = db.Column(db.String(255))

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
