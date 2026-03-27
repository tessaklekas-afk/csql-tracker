import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from models import CSQL, db


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///csql.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.template_filter("currency")
    def format_currency(value):
        if value is None:
            return "—"
        if value >= 1_000_000:
            return f"${value / 1_000_000:.1f}m"
        return f"${value / 1_000:.0f}k"

    @app.template_filter("scorecolor")
    def score_color(value):
        if value is None:
            return "gray"
        if value <= 15:
            return "green"
        if value <= 33:
            return "yellow"
        return "red"

    register_routes(app)
    return app


def get_ad_list():
    raw = os.getenv("AD_LIST", "")
    ads = []
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            name, email = entry.split(":", 1)
            ads.append({"name": name.strip(), "email": email.strip()})
    return ads


def register_routes(app):

    # ──────────────────────────────────────────────
    # Main index — three tabs
    # ──────────────────────────────────────────────
    @app.route("/")
    def index():
        tab = request.args.get("tab", "1")
        ads = get_ad_list()

        accounts = []
        sfdc_opps = {}
        submitted_ids = set()
        error = None

        csqls = []
        status_filter = ""

        if tab == "1":
            try:
                import churnzero
                accounts = churnzero.get_high_health_accounts(min_score=70, top=50)
                # Bulk SFDC check
                import sfdc
                names = [a["Name"] for a in accounts]
                sfdc_opps = sfdc.check_expansion_opps_bulk(names)
                # Mark accounts already pending
                pending = CSQL.query.filter_by(status="pending").all()
                submitted_ids = {c.account_external_id for c in pending}
            except Exception as e:
                error = str(e)

        elif tab == "3":
            status_filter = request.args.get("status", "")
            q = CSQL.query
            if status_filter:
                q = q.filter(CSQL.status == status_filter)
            csqls = q.order_by(CSQL.submitted_at.desc()).all()

        return render_template(
            "index.html",
            tab=tab,
            ads=ads,
            accounts=accounts,
            sfdc_opps=sfdc_opps,
            submitted_ids=submitted_ids,
            error=error,
            csqls=csqls,
            status_filter=status_filter,
        )

    # ──────────────────────────────────────────────
    # Submit CSQL (Tab 1 modal + Tab 2 form)
    # ──────────────────────────────────────────────
    @app.route("/csql/submit", methods=["POST"])
    def csql_submit():
        account_external_id = request.form.get("account_external_id", "").strip()
        account_name = request.form.get("account_name", "").strip()
        submitted_by_name = request.form.get("submitted_by_name", "").strip()
        submitted_by_email = request.form.get("submitted_by_email", "").strip()
        notes = request.form.get("notes", "").strip()
        ad_email = request.form.get("ad_email", "").strip()

        if not all([account_external_id, account_name, submitted_by_name, ad_email]):
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("index", tab=request.form.get("source_tab", "2")))

        # Parse suggested_arr
        suggested_arr = None
        raw_arr = request.form.get("suggested_arr", "").strip()
        if raw_arr:
            try:
                suggested_arr = float(raw_arr)
            except ValueError:
                flash("Invalid ARR value.", "error")
                return redirect(url_for("index", tab=request.form.get("source_tab", "2")))

        # Parse suggested_close_date
        suggested_close_date = None
        raw_date = request.form.get("suggested_close_date", "").strip()
        if raw_date:
            try:
                suggested_close_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid close date.", "error")
                return redirect(url_for("index", tab=request.form.get("source_tab", "2")))

        # Duplicate check: block if pending CSQL already exists for this account
        existing = CSQL.query.filter_by(
            account_external_id=account_external_id, status="pending"
        ).first()
        if existing:
            flash(
                f"A pending CSQL already exists for {account_name}. "
                "Check the Status tab.", "error"
            )
            return redirect(url_for("index", tab=request.form.get("source_tab", "1")))

        # Parse expansion_date
        expansion_date = None
        raw_exp = request.form.get("expansion_date", "").strip()
        if raw_exp:
            try:
                expansion_date = datetime.strptime(raw_exp, "%Y-%m-%d").date()
            except ValueError:
                pass

        csql = CSQL(
            account_external_id=account_external_id,
            account_name=account_name,
            account_health_score=_parse_float(request.form.get("account_health_score")),
            account_mau=_parse_float(request.form.get("account_mau")),
            account_contract_value=_parse_float(request.form.get("account_contract_value")),
            account_renewal_date=request.form.get("account_renewal_date", "").strip() or None,
            account_next_renewal_amount=_parse_float(request.form.get("account_next_renewal_amount")),
            account_api_utilization=_parse_float(request.form.get("account_api_utilization")),
            account_contact_count=_parse_int(request.form.get("account_contact_count")),
            submitted_by_name=submitted_by_name,
            submitted_by_email=submitted_by_email,
            notes=notes,
            suggested_arr=suggested_arr,
            suggested_close_date=suggested_close_date,
            ad_email=ad_email,
            expansion_reason=request.form.get("expansion_reason", "").strip() or None,
            expansion_signal=request.form.get("expansion_signal", "").strip() or None,
            expansion_date=expansion_date,
            primary_product_opportunity=request.form.get("primary_product_opportunity", "").strip() or None,
            contact_external_id=request.form.get("contact_external_id", "").strip() or None,
            contact_name=request.form.get("contact_name", "").strip() or None,
        )
        db.session.add(csql)
        db.session.commit()

        base_url = os.getenv("APP_BASE_URL", "http://localhost:5001").rstrip("/")
        magic_link = f"{base_url}/csql/action/{csql.magic_token}"

        from slack import send_csql_notification
        send_csql_notification(csql, magic_link)

        flash(f"CSQL submitted for {account_name}! The AD has been notified.", "success")
        return redirect(url_for("index", tab="3"))

    # ──────────────────────────────────────────────
    # API: account search (Tab 2 live search)
    # ──────────────────────────────────────────────
    @app.route("/api/account-search")
    def api_account_search():
        q = request.args.get("q", "").strip()
        if len(q) < 2:
            return jsonify([])
        try:
            import churnzero
            accounts = churnzero.search_accounts_by_name(q, top=15)
            return jsonify([
                {
                    "external_id": a.get("ExternalId", ""),
                    "cz_id": a.get("Id"),
                    "name": a.get("Name", ""),
                    "score": a.get("PrimaryChurnScoreValue"),
                    "mau": (a.get("Cf") or {}).get("MonthlyActiveUserCount"),
                    "arr": a.get("TotalContractAmount"),
                    "next_renewal_amount": (a.get("Cf") or {}).get("NextRenewalAmount"),
                    "api_utilization": (a.get("Cf") or {}).get("ApisUsedThisContractYear"),
                    "renewal": a.get("NextRenewalDate", "")[:10] if a.get("NextRenewalDate") else "",
                    "contacts": a.get("ContactsCount"),
                }
                for a in accounts
            ])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ──────────────────────────────────────────────
    # API: account detail by external ID (Tab 2)
    # ──────────────────────────────────────────────
    @app.route("/api/account/<path:external_id>")
    def api_account_detail(external_id):
        try:
            import churnzero
            a = churnzero.get_account_by_external_id(external_id)
            if not a:
                return jsonify(None)
            cf = a.get("Cf") or {}
            return jsonify({
                "external_id": a.get("ExternalId", ""),
                "cz_id": a.get("Id"),
                "name": a.get("Name", ""),
                "score": a.get("PrimaryChurnScoreValue"),
                "mau": cf.get("MonthlyActiveUserCount"),
                "arr": a.get("TotalContractAmount"),
                "next_renewal_amount": cf.get("NextRenewalAmount"),
                "api_utilization": cf.get("ApisUsedThisContractYear"),
                "renewal": a.get("NextRenewalDate", "")[:10] if a.get("NextRenewalDate") else "",
                "contacts": a.get("ContactsCount"),
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ──────────────────────────────────────────────
    # API: contacts for account (by internal CZ ID)
    # ──────────────────────────────────────────────
    @app.route("/api/contacts/<int:cz_id>")
    def api_contacts(cz_id):
        try:
            import churnzero
            contacts = churnzero.get_contacts_for_account(cz_id, top=100)
            return jsonify([
                {
                    "external_id": c.get("ContactExternalId", ""),
                    "name": f"{c.get('FirstName', '')} {c.get('LastName', '')}".strip(),
                    "email": c.get("Email", ""),
                    "title": c.get("Title", ""),
                }
                for c in contacts
                if (c.get("FirstName") or c.get("LastName"))
            ])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ──────────────────────────────────────────────
    # Magic link action page
    # ──────────────────────────────────────────────
    @app.route("/csql/action/<token>")
    def csql_action(token):
        csql = CSQL.query.filter_by(magic_token=token).first_or_404()
        return render_template("action.html", csql=csql)

    @app.route("/csql/action/<token>/accept", methods=["POST"])
    def csql_accept(token):
        csql = CSQL.query.filter_by(magic_token=token).first_or_404()
        if csql.status != "pending":
            return render_template("action.html", csql=csql)
        csql.pipeline_created = True
        csql.status = "accepted"
        csql.pipeline_accepted_arr = _parse_float(request.form.get("confirmed_arr"))
        raw_date = request.form.get("confirmed_close_date", "").strip()
        if raw_date:
            try:
                csql.pipeline_accepted_close_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        csql.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return render_template("action.html", csql=csql)

    @app.route("/csql/action/<token>/decline", methods=["POST"])
    def csql_decline(token):
        csql = CSQL.query.filter_by(magic_token=token).first_or_404()
        if csql.status != "pending":
            return render_template("action.html", csql=csql)
        csql.status = "declined"
        csql.ad_response_notes = request.form.get("reason", "").strip()
        csql.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return render_template("action.html", csql=csql)

    @app.route("/csql/action/<token>/opp-exists", methods=["POST"])
    def csql_opp_exists(token):
        csql = CSQL.query.filter_by(magic_token=token).first_or_404()
        if csql.status != "pending":
            return render_template("action.html", csql=csql)
        csql.expansion_opportunity_exists = True
        csql.expansion_opportunity_id = request.form.get("sfdc_opp_id", "").strip() or None
        csql.status = "accepted"
        csql.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return render_template("action.html", csql=csql)


def _parse_float(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_int(val):
    if val is None or str(val).strip() == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5001)
