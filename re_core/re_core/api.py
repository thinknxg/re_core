from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
import frappe
from frappe import _
from frappe.utils import add_days, today, flt

VAT_RATES = {
    "Oman": 5,
    "United Arab Emirates": 5,
    "Saudi Arabia": 15,
    "Bahrain": 10,
    "Qatar": 0,
    "Kuwait": 0,
}
COUNTRY_CURRENCY = {
    "Oman": "OMR",
    "United Arab Emirates": "AED",
    "Saudi Arabia": "SAR",
    "Bahrain": "BHD",
    "Qatar": "QAR",
    "Kuwait": "KWD",
}


@frappe.whitelist()
def get_properties_list():
    properties = frappe.get_all(
        "Property",
        fields=["name", "property_name", "status", "country", "city", "area", "total_units", "property_type"],
        order_by="modified desc",
    )

    prop_names = [p["name"] for p in properties]
    photo_rows = frappe.get_all(
        "Property Photo",
        filters={"parent": ["in", prop_names], "parenttype": "Property"},
        fields=["parent", "image", "is_cover"],
        order_by="is_cover desc",
    ) if prop_names else []
    cover_map = {}
    for row in photo_rows:
        if row["parent"] not in cover_map:
            cover_map[row["parent"]] = row["image"]

    for p in properties:
        units = frappe.get_all(
            "Unit",
            filters={"property": p["name"]},
            fields=["area_sqm", "annual_rent", "status"],
        )
        rents = [u["annual_rent"] / 12 for u in units if u["annual_rent"]]
        p["rent_min"] = min(rents) if rents else 0
        p["rent_max"] = max(rents) if rents else 0
        p["total_area_sqm"] = sum(u["area_sqm"] or 0 for u in units)
        p["currency"] = COUNTRY_CURRENCY.get(p["country"], "")
        p["vat_rate"] = VAT_RATES.get(p["country"], 5)
        p["vacant_units"] = sum(1 for u in units if u.get("status") == "Vacant")
        p["cover_photo"] = cover_map.get(p["name"])
    return properties


@frappe.whitelist()
def get_sidebar_counts():
    return {
        "units": frappe.db.count("Unit"),
        "contracts": frappe.db.count("Lease Contract", {"status": ["in", ["Draft", "Expiring"]]}),
        "work_orders": frappe.db.count("Maintenance Job", {"completion_date": ["is", "not set"]}),
    }


@frappe.whitelist()
def get_notifications():
    items = []

    upcoming_limit = add_days(today(), 60)
    expiring_count = frappe.db.count(
        "Lease Contract",
        {"status": ["in", ["Active", "Expiring"]],
         "end_date": ["between", [today(), upcoming_limit]]},
    )
    if expiring_count:
        items.append({
            "type": "contracts_expiring",
            "label": f"{expiring_count} lease{'s' if expiring_count != 1 else ''} expiring in the next 60 days",
            "count": expiring_count,
            "screen": "tenants",
        })

    overdue_row = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM `tabRent Installment`
           WHERE status = 'Overdue'"""
    )[0]
    if overdue_row[1]:
        items.append({
            "type": "overdue_rent",
            "label": f"{overdue_row[1]} overdue rent installment{'s' if overdue_row[1] != 1 else ''}",
            "count": overdue_row[1],
            "screen": "rent_schedule",
        })

    open_work_orders = frappe.db.count("Maintenance Job", {"completion_date": ["is", "not set"]})
    if open_work_orders:
        items.append({
            "type": "open_work_orders",
            "label": f"{open_work_orders} open work order{'s' if open_work_orders != 1 else ''}",
            "count": open_work_orders,
            "screen": "maintenance",
        })

    sla_breached_count = frappe.db.count("RE Lead", {"status": "New", "sla_breached": 1})
    if sla_breached_count:
        items.append({
            "type": "sla_breached_leads",
            "label": f"{sla_breached_count} lead{'s' if sla_breached_count != 1 else ''} past SLA, not yet contacted",
            "count": sla_breached_count,
            "screen": "crm",
        })

    return {
        "total": sum(i["count"] for i in items),
        "items": items,
    }


@frappe.whitelist()
def get_dashboard_stats():
    total_properties = frappe.db.count("Property")

    total_units = frappe.db.count("Unit")
    occupied_units = frappe.db.count("Unit", {"status": "Occupied"})
    occupancy_rate = round((occupied_units / total_units) * 100, 1) if total_units else 0

    active_leases = frappe.get_all(
        "Lease Contract",
        filters={"status": "Active"},
        fields=["total_contract_value", "duration_months"],
    )
    monthly_rent_income = sum(
        (l["total_contract_value"] / l["duration_months"])
        for l in active_leases
        if l["total_contract_value"] and l["duration_months"]
    )

    upcoming_limit = add_days(today(), 30)
    pending_renewals = frappe.db.count(
        "Lease Contract",
        {
            "status": ["in", ["Active", "Expiring"]],
            "end_date": ["between", [today(), upcoming_limit]],
        },
    )

    jurisdiction_rows = frappe.get_all(
        "Property",
        fields=["country"],
    )
    jurisdiction_counts = {}
    for row in jurisdiction_rows:
        c = row["country"]
        jurisdiction_counts[c] = jurisdiction_counts.get(c, 0) + 1
    portfolio_by_jurisdiction = [
        {
            "country": country,
            "count": count,
            "vat_rate": VAT_RATES.get(country, 5),
        }
        for country, count in sorted(jurisdiction_counts.items(), key=lambda x: -x[1])
    ]

    total_props_for_reg = total_properties or 1
    ejari_filled = frappe.db.count("Property", {"ejari_number": ["is", "set"]})
    tawtheeq_filled = frappe.db.count("Property", {"tawtheeq_ref": ["is", "set"]})
    municipality_filled = frappe.db.count("Property", {"municipality_ref": ["is", "set"]})
    rera_filled = frappe.db.count("Property", {"rera_permit": ["is", "set"]})

    regulatory_status = {
        "ejari": {"filled": ejari_filled, "total": total_properties},
        "tawtheeq": {"filled": tawtheeq_filled, "total": total_properties},
        "municipality": {"filled": municipality_filled, "total": total_properties},
        "rera": {"filled": rera_filled, "total": total_properties},
    }

    return {
        "total_properties": total_properties,
        "occupancy_rate": occupancy_rate,
        "monthly_rent_income": monthly_rent_income,
        "pending_renewals": pending_renewals,
        "portfolio_by_jurisdiction": portfolio_by_jurisdiction,
        "regulatory_status": regulatory_status,
    }


# ─────────────────────────────────────────────
# UNITS
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_units_list():
    total = frappe.db.count("Unit")
    occupied = frappe.db.count("Unit", {"status": "Occupied"})
    vacant = frappe.db.count("Unit", {"status": "Vacant"})
    under_maintenance = frappe.db.count("Unit", {"status": "Under Maintenance"})

    rows = frappe.get_all(
        "Unit",
        fields=["name", "unit_no", "property", "unit_type", "floor", "area_sqm",
                "bedrooms", "annual_rent", "status"],
        order_by="modified desc",
        limit_page_length=200,
    )
    prop_names = list({r["property"] for r in rows if r["property"]})
    prop_map = {
        p["name"]: p["property_name"]
        for p in frappe.get_all("Property", filters={"name": ["in", prop_names]},
                                 fields=["name", "property_name"])
    } if prop_names else {}
    for r in rows:
        r["property_name"] = prop_map.get(r["property"], r["property"])

    return {
        "stats": {"total": total, "occupied": occupied, "vacant": vacant,
                  "under_maintenance": under_maintenance},
        "rows": rows,
    }


# ─────────────────────────────────────────────
# TENANTS
# ─────────────────────────────────────────────
@frappe.whitelist()
def global_search(query):
    query = (query or "").strip()
    if not query or len(query) < 2:
        return []
    like = "%" + query + "%"
    properties = frappe.get_all(
        "Property",
        filters={"property_name": ["like", like]},
        fields=["name", "property_name", "city"],
        limit_page_length=8,
    )
    tenants = frappe.get_all(
        "Tenant",
        filters={"tenant_name": ["like", like]},
        fields=["name", "tenant_name", "nationality"],
        limit_page_length=8,
    )
    results = []
    for p in properties:
        results.append({
            "type": "Property",
            "name": p["name"],
            "label": p["property_name"],
            "subtitle": p.get("city") or "",
        })
    for t in tenants:
        results.append({
            "type": "Tenant",
            "name": t["name"],
            "label": t["tenant_name"],
            "subtitle": t.get("nationality") or "",
        })
    return results


@frappe.whitelist()
def get_tenants_list():
    active_tenants = frappe.db.count("Tenant", {"disabled": 0})

    upcoming_limit = add_days(today(), 60)
    expiring_soon = frappe.db.count(
        "Lease Contract",
        {"status": ["in", ["Active", "Expiring"]],
         "end_date": ["between", [today(), upcoming_limit]]},
    )

    pdc_held = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0) FROM `tabPost Dated Cheque`
           WHERE status IN ('Received', 'Deposited')""",
    )[0][0] or 0

    avg_duration = frappe.db.sql(
        """SELECT AVG(duration_months) FROM `tabLease Contract`
           WHERE status IN ('Active', 'Expiring', 'Renewed')""",
    )[0][0] or 0

    tenants = frappe.get_all(
        "Tenant",
        filters={"disabled": 0, "request_source": ["!=", "Portal"]},
        fields=["name", "tenant_name", "nationality", "tenant_type", "mobile", "email",
                 "whatsapp_number", "enable_portal", "emergency_contact_name",
                 "emergency_contact_mobile", "disabled"],
        order_by="modified desc",
        limit_page_length=200,
    )
    rows = []
    for t in tenants:
        lease = frappe.get_all(
            "Lease Contract",
            filters={"tenant": t["name"], "status": ["in", ["Active", "Expiring"]]},
            fields=["unit", "start_date", "end_date", "total_contract_value",
                     "duration_months", "payment_frequency", "status"],
            order_by="end_date desc",
            limit_page_length=1,
        )
        lease = lease[0] if lease else {}
        unit_no = frappe.db.get_value("Unit", lease.get("unit"), "unit_no") if lease.get("unit") else None
        monthly_rent = (
            round(lease["total_contract_value"] / lease["duration_months"], 2)
            if lease.get("total_contract_value") and lease.get("duration_months") else None
        )
        rows.append({
            "name": t["name"],
            "tenant_name": t["tenant_name"],
            "nationality": t["nationality"],
            "tenant_type": t["tenant_type"],
            "mobile": t["mobile"],
            "email": t["email"],
            "whatsapp_number": t["whatsapp_number"],
            "enable_portal": t["enable_portal"],
            "emergency_contact_name": t["emergency_contact_name"],
            "emergency_contact_mobile": t["emergency_contact_mobile"],
            "disabled": t["disabled"],
            "unit": unit_no,
            "lease_start": lease.get("start_date"),
            "lease_end": lease.get("end_date"),
            "monthly_rent": monthly_rent,
            "payment_frequency": lease.get("payment_frequency"),
            "status": lease.get("status") or "No Active Lease",
        })

    return {
        "stats": {
            "active_tenants": active_tenants,
            "expiring_soon": expiring_soon,
            "pdc_held": pdc_held,
            "avg_duration_months": round(avg_duration, 1),
        },
        "rows": rows,
    }


@frappe.whitelist()
def get_portal_tenants_list():
    """Tenant profiles auto-created from portal signups (via lease requests),
    kept separate from the main Tenant Register to avoid confusing them with
    tenants who actually have signed leases.
    """
    tenants = frappe.get_all(
        "Tenant",
        filters={"request_source": "Portal"},
        fields=["name", "tenant_name", "mobile", "email", "portal_user", "creation"],
        order_by="creation desc",
        limit_page_length=200,
    )
    for t in tenants:
        t["has_lease_request"] = frappe.db.exists("Lease Contract", {"tenant": t["name"]})
    return tenants


# ─────────────────────────────────────────────
# LEASE CONTRACT FORM (create screen)
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_lease_form_options():
    properties = frappe.get_all("Property", fields=["name", "property_name", "country"])
    tenants = frappe.get_all("Tenant", filters={"disabled": 0}, fields=["name", "tenant_name"])
    agents = frappe.get_all("RE Agent", filters={"is_active": 1}, fields=["name", "agent_name"])
    return {"properties": properties, "tenants": tenants, "agents": agents, "vat_rates": VAT_RATES}


@frappe.whitelist()
def get_units_for_property(property):
    return frappe.get_all(
        "Unit",
        filters={"property": property, "status": "Vacant"},
        fields=["name", "unit_no", "unit_type", "area_sqm", "annual_rent"],
    )


@frappe.whitelist()
def create_lease_contract(tenant, unit, property, start_date, end_date,
                           annual_rent, payment_frequency=None, security_deposit=None,
                           agent=None, owner_ref=None, notice_period_days=None, auto_renew=None,
                           custom_installments=None, broker_commission=None,
                           ejari_contract_no=None, terms=None):
    from frappe.utils import month_diff, getdate, flt

    duration_months = month_diff(end_date, start_date)
    term_years = flt(duration_months) / 12
    term_total = flt(annual_rent) * term_years if term_years > 0 else flt(annual_rent)

    doc = frappe.get_doc({
        "doctype": "Lease Contract",
        "tenant": tenant,
        "unit": unit,
        "property": property,
        "owner_ref": owner_ref,
        "start_date": start_date,
        "end_date": end_date,
        "payment_frequency": payment_frequency or "Monthly",
        "security_deposit_amount": security_deposit or 0,
        "notice_period_days": notice_period_days,
        "auto_renew": auto_renew,
        "custom_installments": custom_installments,
        "broker_commission": broker_commission,
        "ejari_contract_no": ejari_contract_no,
        "terms": terms,
        "status": "Draft",
        "request_source": "Admin",
        "charges": [{
            "charge_type": "Rent",
            "description": "Base Rent",
            "amount": term_total,
        }],
    })
    doc.insert()

    result = {"name": doc.name}
    if agent:
        commission_name = _draft_portal_commission(doc, agent)
        if commission_name:
            result["commission_entry"] = commission_name
    return result


@frappe.whitelist()
def submit_lease_contract(name):
    doc = frappe.get_doc("Lease Contract", name)
    if doc.docstatus != 0:
        frappe.throw(_("Only Draft contracts can be submitted."))
    doc.submit()

    if doc.tenant and frappe.db.get_value("Tenant", doc.tenant, "request_source") == "Portal":
        frappe.db.set_value("Tenant", doc.tenant, "request_source", "Admin")

    return {"name": doc.name, "status": doc.status, "docstatus": doc.docstatus}


def _draft_portal_commission(lease_contract_doc, agent):
    """Draft a Commission Entry for a contract created directly from the portal
    (no CRM Deal in the picture). Mirrors RE Deal._draft_commission()."""
    from re_crm.re_crm.doctype.re_deal.re_deal import compute_commission
    from frappe.utils import flt

    agent_doc = frappe.get_doc("RE Agent", agent)
    base = flt(lease_contract_doc.total_contract_value)
    amount = compute_commission(agent_doc, base)
    if not amount:
        return None

    entry = frappe.new_doc("Commission Entry")
    entry.agent = agent
    entry.lease_contract = lease_contract_doc.name
    entry.company = lease_contract_doc.company
    entry.base_amount = base
    entry.commission_amount = amount
    entry.insert(ignore_permissions=True)
    return entry.name


# ─────────────────────────────────────────────
# INVOICES & PDC SCHEDULE
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_invoices_list():
    month_start = frappe.utils.get_first_day(today())
    month_end = frappe.utils.get_last_day(today())

    outstanding = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0) FROM `tabRent Installment`
           WHERE status IN ('Pending', 'Overdue')"""
    )[0][0] or 0

    collected = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0) FROM `tabRent Installment`
           WHERE status = 'Paid' AND due_date BETWEEN %s AND %s""",
        (month_start, month_end),
    )[0][0] or 0

    upcoming_limit = add_days(today(), 30)
    pdc_upcoming = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0) FROM `tabPost Dated Cheque`
           WHERE status IN ('Received', 'Deposited')
           AND cheque_date BETWEEN %s AND %s""",
        (today(), upcoming_limit),
    )[0][0] or 0

    overdue_row = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM `tabRent Installment`
           WHERE status = 'Overdue'"""
    )[0]

    rows_raw = frappe.db.sql(
        """
        SELECT ri.sales_invoice, ri.due_date, ri.amount, ri.status, ri.pdc,
               rs.tenant, lc.unit, lc.property, t.tenant_name
        FROM `tabRent Installment` ri
        JOIN `tabRent Schedule` rs ON ri.parent = rs.name
        JOIN `tabLease Contract` lc ON rs.lease_contract = lc.name
        LEFT JOIN `tabTenant` t ON rs.tenant = t.name
        ORDER BY ri.due_date DESC
        LIMIT 100
        """,
        as_dict=True,
    )
    prop_names = list({r["property"] for r in rows_raw if r["property"]})
    prop_map = {
        p["name"]: p["country"]
        for p in frappe.get_all("Property", filters={"name": ["in", prop_names]},
                                 fields=["name", "country"])
    } if prop_names else {}
    unit_names = list({r["unit"] for r in rows_raw if r["unit"]})
    unit_map = {
        u["name"]: u["unit_no"]
        for u in frappe.get_all("Unit", filters={"name": ["in", unit_names]},
                                 fields=["name", "unit_no"])
    } if unit_names else {}

    rows = []
    for r in rows_raw:
        country = prop_map.get(r["property"])
        vat_rate = VAT_RATES.get(country, 5)
        rent = r["amount"] or 0
        vat = round(rent * vat_rate / 100, 3)
        rows.append({
            "invoice": r["sales_invoice"] or "—",
            "tenant_name": r["tenant_name"],
            "unit": unit_map.get(r["unit"], r["unit"]),
            "due_date": r["due_date"],
            "rent": rent,
            "vat": vat,
            "vat_rate": vat_rate,
            "total": round(rent + vat, 3),
            "type": "PDC" if r["pdc"] else "Bank",
            "status": r["status"],
        })

    return {
        "stats": {
            "outstanding": outstanding,
            "collected": collected,
            "pdc_upcoming": pdc_upcoming,
            "overdue_amount": overdue_row[0],
            "overdue_count": overdue_row[1],
        },
        "rows": rows,
    }


# ─────────────────────────────────────────────
# COMPLIANCE
# NOTE: Ejari (Dubai) vs Tawtheeq (Abu Dhabi) are both UAE at country level;
# split here by city text match since there's no emirate field on Property.
# Adjust the city keywords below if your data uses different naming.
# ─────────────────────────────────────────────
@frappe.whitelist()
def delete_invoice(name):
    frappe.delete_doc("Sales Invoice", name)
    return {"deleted": name}


@frappe.whitelist()
def get_compliance_status():
    def reg_block(filters, ref_field):
        total = frappe.db.count("Property", filters)
        filled = frappe.db.count("Property", {**filters, ref_field: ["is", "set"]})
        return {"total": total, "filled": filled, "pending": total - filled}

    dubai_filters = {"country": "United Arab Emirates", "city": ["like", "%Dubai%"]}
    abudhabi_filters = {"country": "United Arab Emirates", "city": ["like", "%Abu Dhabi%"]}
    oman_filters = {"country": "Oman"}
    ksa_filters = {"country": "Saudi Arabia"}

    return {
        "ejari": reg_block(dubai_filters, "ejari_number"),
        "tawtheeq": reg_block(abudhabi_filters, "tawtheeq_ref"),
        "municipality": reg_block(oman_filters, "municipality_ref"),
        "rega": reg_block(ksa_filters, "rera_permit"),
    }


# ─────────────────────────────────────────────
# CRM PIPELINE
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_crm_pipeline():
    open_inquiries = frappe.db.count("RE Lead", {"status": ["in", ["New", "Contacted"]]})

    week_start = frappe.utils.get_first_day_of_week(today())
    week_end = add_days(week_start, 6)
    viewings_this_week = frappe.db.count(
        "Site Visit",
        {"visit_datetime": ["between", [week_start, week_end]]},
    )

    applications_under_review = frappe.db.count("RE Deal", {"pipeline_stage": "Negotiation"})

    avg_days_row = frappe.db.sql(
        """
        SELECT AVG(DATEDIFF(d.expected_close, l.first_contacted_on))
        FROM `tabRE Deal` d
        JOIN `tabRE Lead` l ON d.lead = l.name
        WHERE d.pipeline_stage = 'Won' AND l.first_contacted_on IS NOT NULL
        """
    )
    avg_time_to_lease = avg_days_row[0][0] if avg_days_row and avg_days_row[0][0] else None

    stages = ["New", "Contacted", "Site Visit Scheduled", "Negotiation", "Reservation", "Won"]
    deals = frappe.get_all(
        "RE Deal",
        filters={"pipeline_stage": ["in", stages]},
        fields=["name", "title", "tenant_name", "unit", "pipeline_stage",
                "expected_value", "interest_type"],
        order_by="modified desc",
        limit_page_length=200,
    )
    unit_names = list({d["unit"] for d in deals if d["unit"]})
    unit_map = {
        u["name"]: u["unit_no"]
        for u in frappe.get_all("Unit", filters={"name": ["in", unit_names]},
                                 fields=["name", "unit_no"])
    } if unit_names else {}
    for d in deals:
        d["unit_no"] = unit_map.get(d["unit"], d["unit"])

    columns = {stage: [] for stage in stages}
    for d in deals:
        columns[d["pipeline_stage"]].append(d)

    return {
        "stats": {
            "open_inquiries": open_inquiries,
            "viewings_this_week": viewings_this_week,
            "applications_under_review": applications_under_review,
            "avg_time_to_lease": round(avg_time_to_lease, 1) if avg_time_to_lease else None,
        },
        "columns": columns,
    }


# ─────────────────────────────────────────────
# VIEWINGS (SITE VISITS)
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_viewings_list():
    visits = frappe.get_all(
        "Site Visit",
        fields=["name", "deal", "unit", "visit_datetime", "agent", "client_mobile", "outcome"],
        order_by="visit_datetime desc",
        limit_page_length=100,
    )
    deal_names = list({v["deal"] for v in visits if v["deal"]})
    deal_map = {
        d["name"]: d["tenant_name"]
        for d in frappe.get_all("RE Deal", filters={"name": ["in", deal_names]},
                                 fields=["name", "tenant_name"])
    } if deal_names else {}
    unit_names = list({v["unit"] for v in visits if v["unit"]})
    unit_map = {
        u["name"]: (u["unit_no"], u["property"])
        for u in frappe.get_all("Unit", filters={"name": ["in", unit_names]},
                                 fields=["name", "unit_no", "property"])
    } if unit_names else {}
    agent_names = list({v["agent"] for v in visits if v["agent"]})
    agent_map = {
        a["name"]: a["agent_name"]
        for a in frappe.get_all("RE Agent", filters={"name": ["in", agent_names]},
                                 fields=["name", "agent_name"])
    } if agent_names else {}

    for v in visits:
        v["tenant_name"] = deal_map.get(v["deal"])
        unit_info = unit_map.get(v["unit"])
        v["unit_no"] = unit_info[0] if unit_info else None
        v["agent_name"] = agent_map.get(v["agent"])

    return visits


# ─────────────────────────────────────────────
# PORTAL (PUBLIC LISTINGS)
# NOTE: no "published" flag exists yet on Unit — this lists all Vacant units.
# Add a Check field like `published_to_portal` on Unit if you want manual control.
# ─────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def get_portal_listings():
    units = frappe.get_all(
        "Unit",
        filters={"status": "Vacant", "published_to_portal": 1},
        fields=["name", "unit_no", "unit_type", "area_sqm", "bedrooms", "bathrooms",
                "annual_rent", "property"],
        limit_page_length=60,
    )
    prop_names = list({u["property"] for u in units if u["property"]})
    prop_map = {
        p["name"]: p
        for p in frappe.get_all("Property", filters={"name": ["in", prop_names]},
                                 fields=["name", "property_name", "city", "area", "country", "property_type"])
    } if prop_names else {}

    rows = []
    for u in units:
        p = prop_map.get(u["property"], {})
        country = p.get("country")
        rows.append({
            "unit_no": u["unit_no"],
            "unit_type": u["unit_type"],
            "area_sqm": u["area_sqm"],
            "bedrooms": u["bedrooms"],
            "bathrooms": u["bathrooms"],
            "monthly_rent": round(u["annual_rent"] / 12, 2) if u["annual_rent"] else None,
            "property_name": p.get("property_name"),
            "property_type": p.get("property_type"),
            "city": p.get("city"),
            "area": p.get("area"),
            "currency": COUNTRY_CURRENCY.get(country, ""),
            "vat_rate": VAT_RATES.get(country, 5),
        })
    return rows


# ─────────────────────────────────────────────
# MAINTENANCE
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_maintenance_list():
    open_wo = frappe.db.count("Maintenance Request", {"status": ["in", ["Open", "In Progress", "On Hold"]]})

    month_start = frappe.utils.get_first_day(today())
    month_end = frappe.utils.get_last_day(today())
    spend_row = frappe.db.sql(
        """SELECT COALESCE(SUM(total_cost), 0) FROM `tabMaintenance Job`
           WHERE completion_date BETWEEN %s AND %s""",
        (month_start, month_end),
    )[0][0] or 0

    avg_resolution_row = frappe.db.sql(
        """SELECT AVG(DATEDIFF(mj.completion_date, mr.creation))
           FROM `tabMaintenance Job` mj
           JOIN `tabMaintenance Request` mr ON mj.maintenance_request = mr.name
           WHERE mj.completion_date IS NOT NULL"""
    )
    avg_resolution = avg_resolution_row[0][0] if avg_resolution_row and avg_resolution_row[0][0] else None

    vendor_invoices_pending = frappe.db.sql(
        """SELECT COALESCE(SUM(total_cost), 0) FROM `tabMaintenance Job`
           WHERE purchase_invoice IS NULL OR purchase_invoice = ''"""
    )[0][0] or 0

    requests = frappe.get_all(
        "Maintenance Request",
        fields=["name", "unit", "property", "tenant", "category", "priority",
                "status", "maintenance_job"],
        order_by="modified desc",
        limit_page_length=100,
    )
    unit_names = list({r["unit"] for r in requests if r["unit"]})
    unit_map = {
        u["name"]: u["unit_no"]
        for u in frappe.get_all("Unit", filters={"name": ["in", unit_names]},
                                 fields=["name", "unit_no"])
    } if unit_names else {}
    job_names = list({r["maintenance_job"] for r in requests if r["maintenance_job"]})
    job_map = {
        j["name"]: j
        for j in frappe.get_all("Maintenance Job",
                                 filters={"name": ["in", job_names]},
                                 fields=["name", "employee", "supplier", "total_cost"])
    } if job_names else {}

    rows = []
    for r in requests:
        job = job_map.get(r["maintenance_job"], {})
        vendor = job.get("supplier") or job.get("employee") or "—"
        rows.append({
            "name": r["name"],
            "category": r["category"],
            "unit": unit_map.get(r["unit"], r["unit"]),
            "reported_by": "Tenant" if r["tenant"] else "Landlord",
            "priority": r["priority"],
            "vendor": vendor,
            "cost": job.get("total_cost"),
            "status": r["status"],
        })

    return {
        "stats": {
            "open_work_orders": open_wo,
            "avg_resolution_days": round(avg_resolution, 1) if avg_resolution else None,
            "spend_this_month": spend_row,
            "vendor_invoices_pending": vendor_invoices_pending,
        },
        "rows": rows,
    }


# ─────────────────────────────────────────────
# PROPERTY DETAIL
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_property_detail(property):
    p = frappe.get_doc("Property", property)

    units = frappe.get_all(
        "Unit",
        filters={"property": property},
        fields=["name", "unit_no", "unit_type", "area_sqm", "annual_rent", "status",
                "current_lease", "published_to_portal"],
    )
    total_units = len(units)
    occupied = len([u for u in units if u["status"] == "Occupied"])
    vacancy = total_units - occupied
    gross_area = sum(u["area_sqm"] or 0 for u in units)

    lease_names = list({u["current_lease"] for u in units if u["current_lease"]})
    lease_map = {}
    if lease_names:
        for l in frappe.get_all("Lease Contract", filters={"name": ["in", lease_names]},
                                 fields=["name", "tenant_name", "end_date", "total_contract_value",
                                          "duration_months"]):
            lease_map[l["name"]] = l

    monthly_revenue = 0
    for u in units:
        lease = lease_map.get(u["current_lease"])
        if lease and lease.get("total_contract_value") and lease.get("duration_months"):
            monthly_revenue += lease["total_contract_value"] / lease["duration_months"]

    unit_rows = []
    for u in units:
        lease = lease_map.get(u["current_lease"], {})
        unit_rows.append({
            "name": u["name"],
            "unit_no": u["unit_no"],
            "unit_type": u["unit_type"],
            "area_sqm": u["area_sqm"],
            "tenant_name": lease.get("tenant_name"),
            "lease_end": lease.get("end_date"),
            "rent": u["annual_rent"],
            "status": u["status"],
            "published_to_portal": u.get("published_to_portal") or 0,
        })

    owner = frappe.get_all("Property Owner", filters={"name": p.owner_ref}, fields=["owner_name"]) if p.owner_ref else []
    owner_name = owner[0]["owner_name"] if owner else None

    return {
        "property_name": p.property_name,
        "property_type": p.property_type,
        "status": p.status,
        "owner_ref": p.owner_ref,
        "country": p.country,
        "city": p.city,
        "area": p.area,
        "address_line": p.address_line,
        "latitude": p.latitude,
        "longitude": p.longitude,
        "municipality_ref": p.municipality_ref,
        "ejari_number": p.ejari_number,
        "tawtheeq_ref": p.tawtheeq_ref,
        "rera_permit": p.rera_permit,
        "notes": p.notes,
        "usage": p.usage,
        "published_to_portal": p.published_to_portal,
        "area_sqm": p.area_sqm,
        "bedrooms": p.bedrooms,
        "bathrooms": p.bathrooms,
        "furnishing": p.furnishing,
        "parking_slots": p.parking_slots,
        "annual_rent": p.annual_rent,
        "current_lease": p.current_lease,
        "ownership_type": p.ownership_type,
        "management_fee_type": p.management_fee_type,
        "management_fee_value": p.management_fee_value,
        "onetime_commission": p.onetime_commission,
        "no_of_floors": p.no_of_floors,
        "is_live": p.is_live,
        "portal_visibility": p.portal_visibility,
        "vat_rate": VAT_RATES.get(p.country, 5),
        "total_units": total_units,
        "occupied": occupied,
        "vacancy": vacancy,
        "gross_area_sqm": gross_area,
        "monthly_revenue": round(monthly_revenue, 2),
        "units": unit_rows,
        "owner_name": owner_name,
        "company": p.company,
    }


# ─────────────────────────────────────────────
# PROPERTY DOCUMENTS
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_property_documents(property):
    return frappe.get_all(
        "Property Document",
        filters={"property": property},
        fields=["name", "document_type", "attachment", "expiry_date", "notes", "creation"],
        order_by="creation desc",
    )


@frappe.whitelist()
def create_property_document(property, document_type, attachment, expiry_date=None, notes=None):
    doc = frappe.get_doc({
        "doctype": "Property Document",
        "property": property,
        "document_type": document_type,
        "attachment": attachment,
        "expiry_date": expiry_date,
        "notes": notes,
    })
    doc.insert()
    return {"name": doc.name}


@frappe.whitelist()
def delete_property_document(name):
    frappe.delete_doc("Property Document", name)
    return {"deleted": name}


# ─────────────────────────────────────────────
# UNIT PORTAL PUBLISH TOGGLE
# ─────────────────────────────────────────────
@frappe.whitelist()
def set_unit_portal_publish(unit, published):
    published = 1 if int(published) else 0
    frappe.db.set_value("Unit", unit, "published_to_portal", published)

    if published:
        property_name = frappe.db.get_value("Unit", unit, "property")
        if property_name and not frappe.db.get_value("Property", property_name, "is_live"):
            prop = frappe.get_doc("Property", property_name)
            prop.is_live = 1
            prop.save(ignore_permissions=True)

    return {"unit": unit, "published_to_portal": published}


# ─────────────────────────────────────────────
# STANDALONE PROPERTY PORTAL PUBLISH TOGGLE
# (properties with zero Units — e.g. a whole villa/shop rented as one entity.
#  Properties that DO have Units go through set_unit_portal_publish per-unit
#  instead; this endpoint refuses to touch those to avoid confusion.)
# ─────────────────────────────────────────────
@frappe.whitelist()
def set_property_portal_publish(property, published):
    published = 1 if int(published) else 0

    unit_count = frappe.db.count("Unit", {"property": property})
    if unit_count:
        frappe.throw(
            _("{0} has {1} unit(s) — publish/unpublish those individually instead.")
            .format(property, unit_count)
        )

    prop = frappe.get_doc("Property", property)
    prop.published_to_portal = published
    if published:
        prop.is_live = 1
    prop.save(ignore_permissions=True)

    return {"property": property, "published_to_portal": prop.published_to_portal, "is_live": prop.is_live}


# ─────────────────────────────────────────────
# PROPERTY FINANCIALS (scoped Rent Installment view)
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_property_financials(property):
    month_start = frappe.utils.get_first_day(today())
    month_end = frappe.utils.get_last_day(today())

    outstanding = frappe.db.sql(
        """SELECT COALESCE(SUM(ri.amount), 0) FROM `tabRent Installment` ri
           JOIN `tabRent Schedule` rs ON ri.parent = rs.name
           JOIN `tabLease Contract` lc ON rs.lease_contract = lc.name
           WHERE lc.property = %s AND ri.status IN ('Pending', 'Overdue')""",
        (property,),
    )[0][0] or 0

    collected = frappe.db.sql(
        """SELECT COALESCE(SUM(ri.amount), 0) FROM `tabRent Installment` ri
           JOIN `tabRent Schedule` rs ON ri.parent = rs.name
           JOIN `tabLease Contract` lc ON rs.lease_contract = lc.name
           WHERE lc.property = %s AND ri.status = 'Paid'
           AND ri.due_date BETWEEN %s AND %s""",
        (property, month_start, month_end),
    )[0][0] or 0

    overdue_row = frappe.db.sql(
        """SELECT COALESCE(SUM(ri.amount), 0), COUNT(*) FROM `tabRent Installment` ri
           JOIN `tabRent Schedule` rs ON ri.parent = rs.name
           JOIN `tabLease Contract` lc ON rs.lease_contract = lc.name
           WHERE lc.property = %s AND ri.status = 'Overdue'""",
        (property,),
    )[0]

    upcoming = frappe.db.sql(
        """SELECT ri.due_date, ri.amount, ri.status, t.tenant_name, u.unit_no
           FROM `tabRent Installment` ri
           JOIN `tabRent Schedule` rs ON ri.parent = rs.name
           JOIN `tabLease Contract` lc ON rs.lease_contract = lc.name
           LEFT JOIN `tabTenant` t ON rs.tenant = t.name
           LEFT JOIN `tabUnit` u ON lc.unit = u.name
           WHERE lc.property = %s AND ri.status IN ('Pending', 'Overdue')
           ORDER BY ri.due_date ASC
           LIMIT 10""",
        (property,),
        as_dict=True,
    )

    return {
        "outstanding": outstanding,
        "collected": collected,
        "overdue_amount": overdue_row[0],
        "overdue_count": overdue_row[1],
        "upcoming": upcoming,
    }

# ─────────────────────────────────────────────
# POST DATED CHEQUES
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_pdc_list(tenant=None, lease_contract=None, status=None, from_date=None, to_date=None):
    filters = {}
    if tenant:
        filters["tenant"] = tenant
    if lease_contract:
        filters["lease_contract"] = lease_contract
    if status:
        filters["status"] = status
    if from_date and to_date:
        filters["cheque_date"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["cheque_date"] = [">=", from_date]
    elif to_date:
        filters["cheque_date"] = ["<=", to_date]

    total_received = frappe.db.count("Post Dated Cheque", {"status": "Received"})
    total_deposited = frappe.db.count("Post Dated Cheque", {"status": "Deposited"})
    total_bounced = frappe.db.count("Post Dated Cheque", {"status": "Bounced"})

    rows = frappe.get_all(
        "Post Dated Cheque",
        filters=filters,
        fields=["name", "tenant", "lease_contract", "cheque_no", "bank", "cheque_date",
                "amount", "status", "deposit_date", "clearance_date", "bounce_reason",
                "deposit_account", "mode_of_payment", "payment_entry"],
        order_by="cheque_date asc",
        limit_page_length=200,
    )

    return {
        "stats": {
            "received": total_received,
            "deposited": total_deposited,
            "bounced": total_bounced,
        },
        "rows": rows,
    }


@frappe.whitelist()
def get_bank_accounts():
    return frappe.get_all(
        "Account",
        filters={"account_type": "Bank", "is_group": 0},
        fields=["name", "account_name", "company"],
        order_by="account_name asc",
        limit_page_length=200,
    )


@frappe.whitelist()
def get_modes_of_payment():
    return frappe.get_all(
        "Mode of Payment",
        fields=["name", "type"],
        order_by="name asc",
        limit_page_length=100,
    )


@frappe.whitelist()
def update_pdc_status(name, status, deposit_date=None, clearance_date=None, bounce_reason=None,
                       deposit_account=None, mode_of_payment=None):
    doc = frappe.get_doc("Post Dated Cheque", name)

    if deposit_account:
        doc.db_set("deposit_account", deposit_account)
    if mode_of_payment:
        doc.db_set("mode_of_payment", mode_of_payment)

    if deposit_date:
        doc.deposit_date = deposit_date
    if clearance_date:
        doc.clearance_date = clearance_date

    if status == "Deposited":
        doc.mark_deposited()
    elif status == "Cleared":
        doc.mark_cleared()
    elif status == "Bounced":
        doc.mark_bounced(reason=bounce_reason)
    else:
        # Fallback for statuses without a dedicated lifecycle method (e.g. "Returned", "Replaced")
        doc._move(status)

    doc.reload()
    return {"name": doc.name, "status": doc.status, "payment_entry": doc.payment_entry}


# ─────────────────────────────────────────────
# RENT SCHEDULE (with nested Rent Installment rows)
# ─────────────────────────────────────────────
@frappe.whitelist()
def delete_pdc(name):
    frappe.delete_doc("Post Dated Cheque", name)
    return {"deleted": name}


@frappe.whitelist()
def get_rent_schedule(lease_contract=None, tenant=None, status=None):
    filters = {}
    if lease_contract:
        filters["lease_contract"] = lease_contract
    if tenant:
        filters["tenant"] = tenant
    if status:
        filters["status"] = status

    schedules = frappe.get_all(
        "Rent Schedule",
        filters=filters,
        fields=["name", "lease_contract", "tenant", "status", "total_amount"],
        order_by="modified desc",
        limit_page_length=100,
    )

    for s in schedules:
        s["installments"] = frappe.get_all(
            "Rent Installment",
            filters={"parent": s["name"]},
            fields=["name", "installment_no", "due_date", "amount", "paid_amount",
                    "outstanding_amount", "status", "pdc", "sales_invoice", "remarks"],
            order_by="installment_no asc",
        )
        s["outstanding_amount"] = sum(flt(i.get("outstanding_amount")) for i in s["installments"])

    all_pdc_names = list({
        i["pdc"] for s in schedules for i in s["installments"] if i.get("pdc")
    })
    pdc_map = {
        p["name"]: p
        for p in frappe.get_all("Post Dated Cheque", filters={"name": ["in", all_pdc_names]},
                                 fields=["name", "cheque_no", "bank"])
    } if all_pdc_names else {}

    for s in schedules:
        for i in s["installments"]:
            pdc_info = pdc_map.get(i.get("pdc"))
            i["pdc_cheque_no"] = pdc_info["cheque_no"] if pdc_info else None
            i["pdc_bank"] = pdc_info["bank"] if pdc_info else None

    return {"rows": schedules}


@frappe.whitelist()
def get_rent_schedule_detail(name):
    doc = frappe.get_doc("Rent Schedule", name)
    installments = [
        {
            "installment_no": row.installment_no,
            "due_date": row.due_date,
            "amount": row.amount,
            "paid_amount": row.paid_amount,
            "outstanding_amount": row.outstanding_amount,
            "status": row.status,
            "pdc": row.pdc,
            "sales_invoice": row.sales_invoice,
            "remarks": row.remarks,
        }
        for row in doc.installments
    ]
    return {
        "name": doc.name,
        "lease_contract": doc.lease_contract,
        "tenant": doc.tenant,
        "status": doc.status,
        "total_amount": doc.total_amount,
        "outstanding_amount": sum(flt(i["outstanding_amount"]) for i in installments),
        "installments": installments,
    }


# ─────────────────────────────────────────────
# SECURITY DEPOSITS
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_security_deposits(tenant=None, lease_contract=None, status=None):
    filters = {}
    if tenant:
        filters["tenant"] = tenant
    if lease_contract:
        filters["lease_contract"] = lease_contract
    if status:
        filters["status"] = status

    held = frappe.db.sql(
        """SELECT COALESCE(SUM(amount), 0) FROM `tabSecurity Deposit`
           WHERE status = 'Held'""",
    )[0][0] or 0

    refunded = frappe.db.sql(
        """SELECT COALESCE(SUM(refunded_amount), 0) FROM `tabSecurity Deposit`
           WHERE status = 'Refunded'""",
    )[0][0] or 0

    rows = frappe.get_all(
        "Security Deposit",
        filters=filters,
        fields=["name", "tenant", "lease_contract", "amount", "received_date", "status",
                "deduction_amount", "deduction_reason", "refunded_amount"],
        order_by="received_date desc",
        limit_page_length=200,
    )

    return {
        "stats": {"held": held, "refunded": refunded},
        "rows": rows,
    }


@frappe.whitelist()
def update_security_deposit(name, status=None, deduction_amount=None, deduction_reason=None, refunded_amount=None):
    from re_core.re_core.security_deposit_accounting import process_refund_or_forfeit

    doc = frappe.get_doc("Security Deposit", name)
    prev_deduction = flt(doc.deduction_amount)
    prev_refunded = flt(doc.refunded_amount)

    if status:
        doc.status = status
    if deduction_amount is not None:
        doc.deduction_amount = deduction_amount
    if deduction_reason:
        doc.deduction_reason = deduction_reason
    if refunded_amount is not None:
        doc.refunded_amount = refunded_amount
    doc.save()

    if doc.docstatus == 1 and status in ("Refunded", "Partially Refunded", "Forfeited"):
        new_deduction = flt(doc.deduction_amount) - prev_deduction
        new_refund = flt(doc.refunded_amount) - prev_refunded
        if new_deduction > 0 or new_refund > 0:
            process_refund_or_forfeit(doc, new_deduction, new_refund)

    return {"name": doc.name, "status": doc.status}


# ─────────────────────────────────────────────
# LEASE CHARGES (child table on Lease Contract via 'charges')
# ─────────────────────────────────────────────
@frappe.whitelist()
def delete_security_deposit(name):
    frappe.delete_doc("Security Deposit", name)
    return {"deleted": name}


@frappe.whitelist()
def get_lease_charges(lease_contract):
    doc = frappe.get_doc("Lease Contract", lease_contract)
    return [
        {
            "name": row.name,
            "charge_type": row.charge_type,
            "description": row.description,
            "amount": row.amount,
            "item_tax_template": row.item_tax_template,
        }
        for row in doc.charges
    ]


@frappe.whitelist()
def add_lease_charge(lease_contract, charge_type, description, amount, item_tax_template=None):
    doc = frappe.get_doc("Lease Contract", lease_contract)
    doc.append("charges", {
        "charge_type": charge_type,
        "description": description,
        "amount": amount,
        "item_tax_template": item_tax_template,
    })
    doc.save()
    return {"lease_contract": lease_contract, "charges_count": len(doc.charges)}


# ─────────────────────────────────────────────
# PROPERTY PHOTOS (child table on Property via 'photos')
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_property_photos(property):
    doc = frappe.get_doc("Property", property)
    return [
        {
            "name": row.name,
            "image": row.image,
            "caption": row.caption,
            "is_cover": row.is_cover,
        }
        for row in doc.photos
    ]


@frappe.whitelist()
def add_property_photo(property, image, caption=None, is_cover=0):
    doc = frappe.get_doc("Property", property)
    doc.append("photos", {
        "image": image,
        "caption": caption,
        "is_cover": int(is_cover),
    })
    doc.save()
    return {"property": property, "photos_count": len(doc.photos)}


@frappe.whitelist()
def set_cover_photo(property, row_name):
    doc = frappe.get_doc("Property", property)
    for row in doc.photos:
        row.is_cover = 1 if row.name == row_name else 0
    doc.save()
    return {"property": property, "cover": row_name}


@frappe.whitelist()
def delete_property_photo(property, row_name):
    doc = frappe.get_doc("Property", property)
    doc.photos = [row for row in doc.photos if row.name != row_name]
    doc.save()
    return {"property": property, "photos_count": len(doc.photos)}


# ─────────────────────────────────────────────
# AMENITIES (standalone list + Property's Table MultiSelect via 'amenities')
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_amenities():
    return frappe.get_all("Amenity", fields=["name", "amenity_name", "icon"], order_by="amenity_name asc")


@frappe.whitelist()
def get_property_amenities(property):
    doc = frappe.get_doc("Property", property)
    amenity_names = [row.amenity for row in doc.amenities]
    if not amenity_names:
        return []
    return frappe.get_all(
        "Amenity",
        filters={"name": ["in", amenity_names]},
        fields=["name", "amenity_name", "icon"],
    )


@frappe.whitelist()
def set_property_amenities(property, amenities):
    # amenities: list of Amenity names (JSON list or comma-separated string)
    if isinstance(amenities, str):
        amenities = frappe.parse_json(amenities)
    doc = frappe.get_doc("Property", property)
    doc.set("amenities", [])
    for a in amenities:
        doc.append("amenities", {"amenity": a})
    doc.save()
    return {"property": property, "amenities_count": len(doc.amenities)}


# ─────────────────────────────────────────────
# UTILITY ACCOUNTS (standalone, linked to Unit)
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_utility_accounts(unit=None):
    filters = {}
    if unit:
        filters["unit"] = unit

    rows = frappe.get_all(
        "Utility Account",
        filters=filters,
        fields=["name", "unit", "utility_type", "provider", "account_number",
                "meter_number", "in_tenant_name"],
        order_by="unit asc, utility_type asc",
        limit_page_length=200,
    )
    return {"rows": rows}


@frappe.whitelist()
def add_utility_account(unit, utility_type, provider=None, account_number=None,
                         meter_number=None, in_tenant_name=0):
    doc = frappe.get_doc({
        "doctype": "Utility Account",
        "unit": unit,
        "utility_type": utility_type,
        "provider": provider,
        "account_number": account_number,
        "meter_number": meter_number,
        "in_tenant_name": int(in_tenant_name),
    }).insert()
    return {"name": doc.name}


@frappe.whitelist()
def update_utility_account(name, utility_type=None, provider=None, account_number=None,
                            meter_number=None, in_tenant_name=None):
    doc = frappe.get_doc("Utility Account", name)
    if utility_type:
        doc.utility_type = utility_type
    if provider is not None:
        doc.provider = provider
    if account_number is not None:
        doc.account_number = account_number
    if meter_number is not None:
        doc.meter_number = meter_number
    if in_tenant_name is not None:
        doc.in_tenant_name = int(in_tenant_name)
    doc.save()
    return {"name": doc.name}


# ─────────────────────────────────────────────
# TENANT KYC DOCUMENTS (child table on Tenant via 'kyc_documents')
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_tenant_kyc_documents(tenant):
    doc = frappe.get_doc("Tenant", tenant)
    return [
        {
            "name": row.name,
            "id_type": row.id_type,
            "id_number": row.id_number,
            "expiry_date": row.expiry_date,
            "attachment": row.attachment,
        }
        for row in doc.kyc_documents
    ]


@frappe.whitelist()
def add_tenant_kyc_document(tenant, id_type, id_number=None, expiry_date=None, attachment=None):
    doc = frappe.get_doc("Tenant", tenant)
    doc.append("kyc_documents", {
        "id_type": id_type,
        "id_number": id_number,
        "expiry_date": expiry_date,
        "attachment": attachment,
    })
    doc.save()
    return {"tenant": tenant, "kyc_documents_count": len(doc.kyc_documents)}


@frappe.whitelist()
def delete_tenant_kyc_document(tenant, row_name):
    doc = frappe.get_doc("Tenant", tenant)
    doc.kyc_documents = [row for row in doc.kyc_documents if row.name != row_name]
    doc.save()
    return {"tenant": tenant, "kyc_documents_count": len(doc.kyc_documents)}


# ─────────────────────────────────────────────
# MOVE IN / OUT INSPECTIONS (standalone, with nested Inspection Item rows)
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_inspections(lease_contract=None, unit=None, inspection_type=None):
    filters = {}
    if lease_contract:
        filters["lease_contract"] = lease_contract
    if unit:
        filters["unit"] = unit
    if inspection_type:
        filters["inspection_type"] = inspection_type

    rows = frappe.get_all(
        "Move In Out Inspection",
        filters=filters,
        fields=["name", "inspection_type", "lease_contract", "unit", "inspection_date",
                "inspected_by", "tenant_present", "estimated_damage_cost", "summary"],
        order_by="inspection_date desc",
        limit_page_length=200,
    )
    return {"rows": rows}


@frappe.whitelist()
def get_inspection_detail(name):
    doc = frappe.get_doc("Move In Out Inspection", name)
    return {
        "name": doc.name,
        "inspection_type": doc.inspection_type,
        "lease_contract": doc.lease_contract,
        "unit": doc.unit,
        "inspection_date": doc.inspection_date,
        "inspected_by": doc.inspected_by,
        "tenant_present": doc.tenant_present,
        "estimated_damage_cost": doc.estimated_damage_cost,
        "summary": doc.summary,
        "tenant_signature": doc.tenant_signature,
        "items": [
            {
                "room": row.room,
                "item": row.item,
                "condition": row.condition,
                "photo": row.photo,
                "remarks": row.remarks,
            }
            for row in doc.items
        ],
    }


@frappe.whitelist()
def create_inspection(inspection_type, lease_contract, unit, inspection_date,
                       inspected_by=None, tenant_present=0, items=None):
    # items: JSON list of {room, item, condition, photo, remarks}
    if isinstance(items, str):
        items = frappe.parse_json(items)

    doc = frappe.get_doc({
        "doctype": "Move In Out Inspection",
        "inspection_type": inspection_type,
        "lease_contract": lease_contract,
        "unit": unit,
        "inspection_date": inspection_date,
        "inspected_by": inspected_by or frappe.session.user,
        "tenant_present": int(tenant_present),
    })
    for row in (items or []):
        doc.append("items", row)
    doc.insert()
    return {"name": doc.name}


@frappe.whitelist()
def update_inspection(name, estimated_damage_cost=None, summary=None, tenant_signature=None):
    doc = frappe.get_doc("Move In Out Inspection", name)
    if estimated_damage_cost is not None:
        doc.estimated_damage_cost = estimated_damage_cost
    if summary is not None:
        doc.summary = summary
    if tenant_signature is not None:
        doc.tenant_signature = tenant_signature
    doc.save()
    return {"name": doc.name}


# ─────────────────────────────────────────────
# LEASE CONTRACTS LIST (for pickers)
# ─────────────────────────────────────────────
@frappe.whitelist()
def terminate_lease_contract(name, termination_date=None, reason=None):
    doc = frappe.get_doc("Lease Contract", name)
    status = doc.terminate(termination_date=termination_date, reason=reason)
    return {"name": doc.name, "status": status}


@frappe.whitelist()
def reject_lease_contract(name):
    doc = frappe.get_doc("Lease Contract", name)
    if doc.docstatus != 0:
        frappe.throw(_("Only Draft requests can be rejected."))
    frappe.delete_doc("Lease Contract", name, ignore_permissions=True)
    return {"deleted": name}


@frappe.whitelist()
def get_property_enquiries_list(status=None):
    filters = {}
    if status:
        filters["status"] = status
    rows = frappe.get_all(
        "Property Enquiry",
        filters=filters,
        fields=["name", "unit", "property", "customer", "linked_lead", "enquiry_type",
                "status", "message", "assigned_to_user", "creation"],
        order_by="creation desc",
        limit_page_length=200,
    )
    unit_names = list({r["unit"] for r in rows if r["unit"]})
    unit_map = {
        u["name"]: u["unit_no"]
        for u in frappe.get_all("Unit", filters={"name": ["in", unit_names]}, fields=["name", "unit_no"])
    } if unit_names else {}
    lead_names = list({r["linked_lead"] for r in rows if r["linked_lead"]})
    lead_map = {
        l["name"]: l["lead_name"]
        for l in frappe.get_all("Lead", filters={"name": ["in", lead_names]}, fields=["name", "lead_name"])
    } if lead_names else {}
    for r in rows:
        r["unit_no"] = unit_map.get(r["unit"], r["unit"])
        r["lead_name"] = lead_map.get(r["linked_lead"])
    return rows


@frappe.whitelist()
def update_property_enquiry(name, status=None, assigned_to_user=None):
    doc = frappe.get_doc("Property Enquiry", name)
    if status is not None:
        doc.status = status
    if assigned_to_user is not None:
        doc.assigned_to_user = assigned_to_user
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def get_site_visit_bookings_list(status=None):
    filters = {}
    if status:
        filters["status"] = status
    rows = frappe.get_all(
        "Site Visit Booking",
        filters=filters,
        fields=["name", "unit", "property", "customer", "lead", "visit_date",
                "visit_time_slot", "status", "assigned_agent", "notes", "creation"],
        order_by="creation desc",
        limit_page_length=200,
    )
    unit_names = list({r["unit"] for r in rows if r["unit"]})
    unit_map = {
        u["name"]: u["unit_no"]
        for u in frappe.get_all("Unit", filters={"name": ["in", unit_names]}, fields=["name", "unit_no"])
    } if unit_names else {}
    lead_names = list({r["lead"] for r in rows if r["lead"]})
    lead_map = {
        l["name"]: l["lead_name"]
        for l in frappe.get_all("Lead", filters={"name": ["in", lead_names]}, fields=["name", "lead_name"])
    } if lead_names else {}
    for r in rows:
        r["unit_no"] = unit_map.get(r["unit"], r["unit"])
        r["lead_name"] = lead_map.get(r["lead"])
    return rows


@frappe.whitelist()
def update_site_visit_booking(name, status=None, assigned_agent=None):
    doc = frappe.get_doc("Site Visit Booking", name)
    if status is not None:
        doc.status = status
    if assigned_agent is not None:
        doc.assigned_agent = assigned_agent
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def get_lease_contracts_list(source="Admin"):
    filters = {}
    if source and source != "All":
        filters["request_source"] = source
    rows = frappe.get_all(
        "Lease Contract",
        filters=filters,
        fields=["name", "tenant", "unit", "property", "status", "docstatus",
                "start_date", "end_date", "total_contract_value", "payment_frequency",
                "rent_schedule", "security_deposit", "request_source"],
        order_by="modified desc",
        limit_page_length=200,
    )
    tenant_names = list({r["tenant"] for r in rows if r["tenant"]})
    tenant_map = {
        t["name"]: t["tenant_name"]
        for t in frappe.get_all("Tenant", filters={"name": ["in", tenant_names]}, fields=["name", "tenant_name"])
    } if tenant_names else {}
    unit_names = list({r["unit"] for r in rows if r["unit"]})
    unit_map = {
        u["name"]: u["unit_no"]
        for u in frappe.get_all("Unit", filters={"name": ["in", unit_names]}, fields=["name", "unit_no"])
    } if unit_names else {}
    for r in rows:
        r["tenant_name"] = tenant_map.get(r["tenant"], r["tenant"])
        r["unit_no"] = unit_map.get(r["unit"], r["unit"])
    return rows


# ─────────────────────────────────────────────
# PDC — CREATE
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_pdc_suggested_amount(lease_contract):
    schedule_name = frappe.db.get_value("Rent Schedule", {"lease_contract": lease_contract}, "name")
    if schedule_name:
        installment = frappe.get_all(
            "Rent Installment",
            filters={"parent": schedule_name, "status": ["in", ["Pending", "Overdue"]]},
            fields=["amount"],
            order_by="installment_no asc",
            limit_page_length=1,
        )
        if installment:
            return {"amount": installment[0]["amount"], "source": "installment"}

    lease = frappe.db.get_value(
        "Lease Contract", lease_contract,
        ["total_contract_value", "duration_months"], as_dict=True,
    )
    if lease and lease.total_contract_value and lease.duration_months:
        return {"amount": round(lease.total_contract_value / lease.duration_months, 2), "source": "estimated"}

    return {"amount": None, "source": None}


@frappe.whitelist()
def get_lease_installments(lease_contract):
    schedule_name = frappe.db.get_value("Rent Schedule", {"lease_contract": lease_contract}, "name")
    if not schedule_name:
        return {"schedule": None, "installments": []}
    installments = frappe.get_all(
        "Rent Installment",
        filters={"parent": schedule_name},
        fields=["name", "installment_no", "due_date", "amount", "status", "pdc"],
        order_by="installment_no asc",
    )
    return {"schedule": schedule_name, "installments": installments}


@frappe.whitelist()
def link_pdc_to_installment(pdc, installment_name):
    parent = frappe.db.get_value("Rent Installment", installment_name, "parent")
    if not parent:
        frappe.throw("Installment not found")
    schedule_doc = frappe.get_doc("Rent Schedule", parent)
    row = next((r for r in schedule_doc.installments if r.name == installment_name), None)
    if not row:
        frappe.throw("Installment not found on schedule")
    row.pdc = pdc

    pdc_status = frappe.db.get_value("Post Dated Cheque", pdc, "status")
    installment_status_map = {
        "Cleared": "Paid",
        "Bounced": "Bounced",
        "Returned": "Cancelled",
    }
    new_status = installment_status_map.get(pdc_status)
    if new_status:
        row.status = new_status

    schedule_doc.save()
    return {"linked": installment_name, "pdc": pdc, "installment_status": row.status}


@frappe.whitelist()
def create_pdc(tenant, cheque_no, bank, cheque_date, amount, lease_contract=None,
                company=None):
    # New PDCs always start at "Received" - all further transitions must go
    # through the mark_deposited/mark_cleared/mark_bounced lifecycle methods,
    # never set directly, so the accounting side-effects always fire.
    doc = frappe.get_doc({
        "doctype": "Post Dated Cheque",
        "tenant": tenant,
        "lease_contract": lease_contract,
        "company": company,
        "cheque_no": cheque_no,
        "bank": bank,
        "cheque_date": cheque_date,
        "amount": amount,
        "status": "Received",
    }).insert()
    doc.submit()

    # Link this PDC to the lease's next unassigned installment, if one exists.
    if lease_contract:
        schedule_name = frappe.db.get_value("Rent Schedule", {"lease_contract": lease_contract}, "name")
        if schedule_name:
            schedule_doc = frappe.get_doc("Rent Schedule", schedule_name)
            candidates = [
                row for row in schedule_doc.installments
                if row.status in ("Pending", "Overdue") and not row.pdc
            ]
            candidates.sort(key=lambda row: row.installment_no)
            if candidates:
                candidates[0].pdc = doc.name
                schedule_doc.save()

    return {"name": doc.name}


# ─────────────────────────────────────────────
# RENT SCHEDULE — CREATE + INSTALLMENT UPDATE
# ─────────────────────────────────────────────
@frappe.whitelist()
def create_rent_schedule(lease_contract, tenant=None, company=None, status="Active",
                          total_amount=None, installments=None):
    if isinstance(installments, str):
        installments = frappe.parse_json(installments)
    doc = frappe.get_doc({
        "doctype": "Rent Schedule",
        "lease_contract": lease_contract,
        "tenant": tenant,
        "company": company,
        "status": status,
        "total_amount": total_amount,
    })
    for row in (installments or []):
        doc.append("installments", row)
    doc.insert()
    return {"name": doc.name}


@frappe.whitelist()
def update_installment_status(rent_schedule, row_name, status, sales_invoice=None, pdc=None, remarks=None):
    doc = frappe.get_doc("Rent Schedule", rent_schedule)
    for row in doc.installments:
        if row.name == row_name:
            row.status = status
            if sales_invoice is not None:
                row.sales_invoice = sales_invoice
            if pdc is not None:
                row.pdc = pdc
            if remarks is not None:
                row.remarks = remarks
    doc.save()
    return {"rent_schedule": rent_schedule, "row_name": row_name, "status": status}


# ─────────────────────────────────────────────
# SECURITY DEPOSIT — CREATE
# ─────────────────────────────────────────────
@frappe.whitelist()
def update_rent_schedule_status(name, status):
    doc = frappe.get_doc("Rent Schedule", name)
    doc.status = status
    doc.save()
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def delete_rent_schedule(name):
    frappe.delete_doc("Rent Schedule", name)
    return {"deleted": name}


@frappe.whitelist()
def create_security_deposit(tenant, lease_contract, amount, company=None,
                             received_date=None, status="Held"):
    doc = frappe.get_doc({
        "doctype": "Security Deposit",
        "tenant": tenant,
        "lease_contract": lease_contract,
        "company": company,
        "amount": amount,
        "received_date": received_date,
        "status": status,
    }).insert()
    return {"name": doc.name}


# ─────────────────────────────────────────────
# LEASE CHARGES — DELETE (edit parity with add_lease_charge)
# ─────────────────────────────────────────────
@frappe.whitelist()
def delete_lease_charge(lease_contract, row_name):
    doc = frappe.get_doc("Lease Contract", lease_contract)
    doc.charges = [row for row in doc.charges if row.name != row_name]
    doc.save()
    return {"lease_contract": lease_contract, "charges_count": len(doc.charges)}


# ─────────────────────────────────────────────
# AMENITIES — CREATE (master data)
# ─────────────────────────────────────────────
@frappe.whitelist()
def create_amenity(amenity_name, icon=None):
    doc = frappe.get_doc({
        "doctype": "Amenity",
        "amenity_name": amenity_name,
        "icon": icon,
    }).insert()
    return {"name": doc.name}


# ─────────────────────────────────────────────
# TENANT KYC — UPDATE (edit parity with add/delete)
# ─────────────────────────────────────────────
@frappe.whitelist()
def update_tenant_kyc_document(tenant, row_name, id_type=None, id_number=None,
                                expiry_date=None, attachment=None):
    doc = frappe.get_doc("Tenant", tenant)
    for row in doc.kyc_documents:
        if row.name == row_name:
            if id_type is not None:
                row.id_type = id_type
            if id_number is not None:
                row.id_number = id_number
            if expiry_date is not None:
                row.expiry_date = expiry_date
            if attachment is not None:
                row.attachment = attachment
    doc.save()
    return {"tenant": tenant, "row_name": row_name}


# ─────────────────────────────────────────────
# INSPECTIONS — UPDATE ITEMS
# ─────────────────────────────────────────────
@frappe.whitelist()
def update_inspection_items(name, items):
    if isinstance(items, str):
        items = frappe.parse_json(items)
    doc = frappe.get_doc("Move In Out Inspection", name)
    doc.set("items", [])
    for row in (items or []):
        doc.append("items", row)
    doc.save()
    return {"name": doc.name, "items_count": len(doc.items)}


# ─────────────────────────────────────────────
# PROPERTY — CREATE
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_companies():
    return frappe.get_all("Company", fields=["name"], order_by="name")


@frappe.whitelist()
def get_property_owners_list():
    return frappe.get_all("Property Owner", fields=["name", "owner_name"], order_by="owner_name asc")


@frappe.whitelist()
def create_property(property_name, property_type, owner_ref, country, company=None,
                     status="Active", city=None, area=None, address_line=None,
                     latitude=None, longitude=None,
                     municipality_ref=None, ejari_number=None, rera_permit=None, tawtheeq_ref=None,
                     notes=None,
                     usage=None, published_to_portal=None,
                     area_sqm=None, bedrooms=None, bathrooms=None, furnishing=None, parking_slots=None,
                     annual_rent=None, current_lease=None,
                     ownership_type=None, management_fee_type=None, management_fee_value=None,
                     onetime_commission=None, no_of_floors=None,
                     is_live=None, portal_visibility=None):
    doc = frappe.get_doc({
        "doctype": "Property",
        "property_name": property_name,
        "property_type": property_type,
        "owner_ref": owner_ref,
        "country": country,
        "company": company,
        "status": status,
        "city": city,
        "area": area,
        "address_line": address_line,
        "latitude": latitude,
        "longitude": longitude,
        "municipality_ref": municipality_ref,
        "ejari_number": ejari_number,
        "rera_permit": rera_permit,
        "tawtheeq_ref": tawtheeq_ref,
        "notes": notes,
        "usage": usage,
        "published_to_portal": published_to_portal,
        "area_sqm": area_sqm,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "furnishing": furnishing,
        "parking_slots": parking_slots,
        "annual_rent": annual_rent,
        "current_lease": current_lease,
        "ownership_type": ownership_type,
        "management_fee_type": management_fee_type,
        "management_fee_value": management_fee_value,
        "onetime_commission": onetime_commission,
        "no_of_floors": no_of_floors,
        "is_live": is_live,
        "portal_visibility": portal_visibility,
    }).insert()
    return {"name": doc.name}


@frappe.whitelist()
def update_property(name, property_name=None, property_type=None, owner_ref=None, country=None,
                     company=None, status=None, city=None, area=None, address_line=None,
                     latitude=None, longitude=None,
                     municipality_ref=None, ejari_number=None, rera_permit=None, tawtheeq_ref=None,
                     notes=None,
                     usage=None, published_to_portal=None,
                     area_sqm=None, bedrooms=None, bathrooms=None, furnishing=None, parking_slots=None,
                     annual_rent=None, current_lease=None,
                     ownership_type=None, management_fee_type=None, management_fee_value=None,
                     onetime_commission=None, no_of_floors=None,
                     is_live=None, portal_visibility=None):
    doc = frappe.get_doc("Property", name)
    fields = {
        "property_name": property_name, "property_type": property_type, "owner_ref": owner_ref,
        "country": country, "company": company, "status": status, "city": city, "area": area,
        "address_line": address_line, "latitude": latitude, "longitude": longitude,
        "municipality_ref": municipality_ref, "ejari_number": ejari_number,
        "rera_permit": rera_permit, "tawtheeq_ref": tawtheeq_ref, "notes": notes,
        "usage": usage, "published_to_portal": published_to_portal,
        "area_sqm": area_sqm, "bedrooms": bedrooms, "bathrooms": bathrooms,
        "furnishing": furnishing, "parking_slots": parking_slots,
        "annual_rent": annual_rent, "current_lease": current_lease,
        "ownership_type": ownership_type, "management_fee_type": management_fee_type,
        "management_fee_value": management_fee_value, "onetime_commission": onetime_commission,
        "no_of_floors": no_of_floors, "is_live": is_live, "portal_visibility": portal_visibility,
    }
    for key, value in fields.items():
        if value is not None:
            doc.set(key, value)
    doc.save()
    return {"name": doc.name}


# ─────────────────────────────────────────────
# UNIT — CREATE
# ─────────────────────────────────────────────
@frappe.whitelist()
def create_unit(property, unit_no, unit_type, unit_title=None, floor=None, usage=None,
                 status="Vacant", area_sqm=None, bedrooms=None, bathrooms=None,
                 furnishing=None, parking_slots=None, annual_rent=None,
                 current_lease=None, company=None,
                 ownership_type=None, owner_ref=None, management_fee_type=None,
                 management_fee_value=None, onetime_commission=None, published_to_portal=None):
    doc = frappe.get_doc({
        "doctype": "Unit",
        "property": property,
        "unit_no": unit_no,
        "unit_type": unit_type,
        "unit_title": unit_title,
        "floor": floor,
        "usage": usage,
        "status": status,
        "area_sqm": area_sqm,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "furnishing": furnishing,
        "parking_slots": parking_slots,
        "annual_rent": annual_rent,
        "current_lease": current_lease,
        "company": company,
        "ownership_type": ownership_type,
        "owner_ref": owner_ref,
        "management_fee_type": management_fee_type,
        "management_fee_value": management_fee_value,
        "onetime_commission": onetime_commission,
        "published_to_portal": published_to_portal,
    }).insert()
    return {"name": doc.name}


@frappe.whitelist()
def update_unit(name, unit_type=None, unit_title=None, floor=None, usage=None, status=None,
                 area_sqm=None, bedrooms=None, bathrooms=None, furnishing=None, parking_slots=None,
                 annual_rent=None, current_lease=None, company=None,
                 ownership_type=None, owner_ref=None, management_fee_type=None,
                 management_fee_value=None, onetime_commission=None, published_to_portal=None):
    doc = frappe.get_doc("Unit", name)
    fields = {
        "unit_type": unit_type, "unit_title": unit_title, "floor": floor, "usage": usage,
        "status": status, "area_sqm": area_sqm, "bedrooms": bedrooms, "bathrooms": bathrooms,
        "furnishing": furnishing, "parking_slots": parking_slots, "annual_rent": annual_rent,
        "current_lease": current_lease, "company": company,
        "ownership_type": ownership_type, "owner_ref": owner_ref,
        "management_fee_type": management_fee_type, "management_fee_value": management_fee_value,
        "onetime_commission": onetime_commission, "published_to_portal": published_to_portal,
    }
    for key, value in fields.items():
        if value is not None:
            doc.set(key, value)
    doc.save()
    return {"name": doc.name}


@frappe.whitelist()
def delete_unit(name):
    frappe.delete_doc("Unit", name)
    return {"deleted": name}


# ─────────────────────────────────────────────
# TENANT — CREATE
# ─────────────────────────────────────────────
@frappe.whitelist()
def create_tenant(tenant_name, mobile, tenant_type=None, nationality=None,
                   email=None, whatsapp_number=None):
    doc = frappe.get_doc({
        "doctype": "Tenant",
        "tenant_name": tenant_name,
        "mobile": mobile,
        "tenant_type": tenant_type,
        "nationality": nationality,
        "email": email,
        "whatsapp_number": whatsapp_number,
    }).insert()
    return {"name": doc.name}


# ─────────────────────────────────────────────
# MAINTENANCE REQUEST — CREATE
# ─────────────────────────────────────────────
@frappe.whitelist()
def update_tenant(name, tenant_name=None, tenant_type=None, nationality=None, mobile=None,
                   email=None, whatsapp_number=None, enable_portal=None,
                   emergency_contact_name=None, emergency_contact_mobile=None, disabled=None):
    doc = frappe.get_doc("Tenant", name)
    if tenant_name is not None:
        doc.tenant_name = tenant_name
    if tenant_type is not None:
        doc.tenant_type = tenant_type
    if nationality is not None:
        doc.nationality = nationality
    if mobile is not None:
        doc.mobile = mobile
    if email is not None:
        doc.email = email
    if whatsapp_number is not None:
        doc.whatsapp_number = whatsapp_number
    if enable_portal is not None:
        doc.enable_portal = enable_portal
    if emergency_contact_name is not None:
        doc.emergency_contact_name = emergency_contact_name
    if emergency_contact_mobile is not None:
        doc.emergency_contact_mobile = emergency_contact_mobile
    if disabled is not None:
        doc.disabled = disabled
    doc.save()
    return {"name": doc.name}


@frappe.whitelist()
def delete_tenant(name):
    frappe.delete_doc("Tenant", name)
    return {"deleted": name}


@frappe.whitelist()
def create_maintenance_request(unit, category, description, property=None, tenant=None,
                                priority="Medium", status="Open"):
    doc = frappe.get_doc({
        "doctype": "Maintenance Request",
        "unit": unit,
        "category": category,
        "description": description,
        "property": property,
        "tenant": tenant,
        "priority": priority,
        "status": status,
    }).insert()
    return {"name": doc.name}



@frappe.whitelist()
def record_partial_payment(installment_name, amount, mode_of_payment="Cash", payment_date=None, remarks=None):
	amount = flt(amount)
	if amount <= 0:
		frappe.throw("Payment amount must be greater than zero.")

	schedule_name = frappe.db.get_value("Rent Installment", installment_name, "parent")
	if not schedule_name:
		frappe.throw(f"Rent Installment {installment_name} not found.")

	schedule_doc = frappe.get_doc("Rent Schedule", schedule_name)

	installments = sorted(
		schedule_doc.installments,
		key=lambda r: (r.due_date or frappe.utils.getdate("9999-12-31"), flt(r.installment_no)),
	)

	start_idx = None
	for idx, r in enumerate(installments):
		if r.name == installment_name:
			start_idx = idx
			break
	if start_idx is None:
		frappe.throw(f"Rent Installment {installment_name} not found in Rent Schedule {schedule_name}.")

	if not installments[start_idx].sales_invoice:
		frappe.throw("This installment has no linked Sales Invoice yet. Generate the invoice before recording a payment.")

	remaining = amount
	applied = []

	for r in installments[start_idx:]:
		if remaining <= 0:
			break
		outstanding = flt(r.amount) - flt(r.paid_amount)
		if outstanding <= 0:
			continue
		if not r.sales_invoice:
			break

		pay_amt = min(remaining, outstanding)

		si = frappe.get_doc("Sales Invoice", r.sales_invoice)
		pe = get_payment_entry("Sales Invoice", si.name, party_amount=pay_amt)
		pe.mode_of_payment = mode_of_payment
		mop_account = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": mode_of_payment, "company": si.company},
			"default_account",
		)
		if mop_account:
			if pe.payment_type == "Receive":
				pe.paid_to = mop_account
			else:
				pe.paid_from = mop_account
		if payment_date:
			pe.posting_date = payment_date
		if remarks:
			pe.remarks = remarks
		pe.insert()
		pe.submit()

		payment_doc = frappe.get_doc({
			"doctype": "Rent Installment Payment",
			"parent": r.name,
			"parenttype": "Rent Installment",
			"parentfield": "payments",
			"payment_date": payment_date or frappe.utils.today(),
			"amount": pay_amt,
			"mode_of_payment": mode_of_payment,
			"payment_entry": pe.name,
			"remarks": remarks,
		})
		payment_doc.insert(ignore_permissions=True)

		new_paid = flt(r.paid_amount) + pay_amt
		new_outstanding = flt(r.amount) - new_paid
		new_status = "Paid" if new_outstanding <= 0 else "Partially Paid"
		frappe.db.set_value("Rent Installment", r.name, {
			"paid_amount": new_paid,
			"outstanding_amount": new_outstanding,
			"status": new_status,
		})

		applied.append({
			"installment": r.name,
			"payment_entry": pe.name,
			"amount_applied": pay_amt,
			"status": new_status,
		})

		remaining = flt(remaining - pay_amt)

	credit_balance = None
	if remaining > 0:
		credit_customer = frappe.db.get_value("Tenant", schedule_doc.tenant, "customer")
		if not credit_customer:
			frappe.throw(f"Tenant {schedule_doc.tenant} has no linked Customer.")
		credit_doc = frappe.get_doc({
			"doctype": "Rent Credit Balance",
			"lease_contract": schedule_doc.lease_contract,
			"tenant": credit_customer,
			"rent_schedule": schedule_doc.name,
			"source_installment": installment_name,
			"amount": remaining,
			"status": "Available",
			"remarks": remarks,
		})
		credit_doc.insert(ignore_permissions=True)
		credit_balance = {
			"credit_balance_name": credit_doc.name,
			"amount": remaining,
		}

	return {
		"installments_paid": applied,
		"credit_created": credit_balance,
	}


# ─────────────────────────────────────────────
# BULK PDC PAYMENT ENTRY
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_bulk_pdc_due_installments(property, from_date, to_date):
    return frappe.db.sql("""
        select
            ri.name as rent_installment,
            ri.due_date,
            ri.amount,
            ri.outstanding_amount,
            rs.lease_contract,
            rs.tenant,
            t.tenant_name
        from `tabRent Installment` ri
        inner join `tabRent Schedule` rs on rs.name = ri.parent
        inner join `tabLease Contract` lc on lc.name = rs.lease_contract
        left join `tabTenant` t on t.name = rs.tenant
        where lc.property = %(property)s
            and ri.due_date between %(from_date)s and %(to_date)s
            and ri.status in ('Pending', 'Partially Paid', 'Overdue')
            and ifnull(ri.sales_invoice, '') != ''
        order by ri.due_date
    """, {"property": property, "from_date": from_date, "to_date": to_date}, as_dict=True)


@frappe.whitelist()
def submit_bulk_pdc_payments(property, rows, mode_of_payment="Cash", company=None):
    if isinstance(rows, str):
        rows = frappe.parse_json(rows)
    if not rows:
        frappe.throw("No rows to process.")
    if not company:
        company = frappe.db.get_value("Property", property, "company")

    results = []
    for row in rows:
        installment_name = row.get("rent_installment")
        pay_amount = flt(row.get("pay_amount"))

        if not installment_name or pay_amount <= 0:
            results.append({"rent_installment": installment_name, "status": "Failed", "error": "Missing installment or pay amount"})
            continue

        savepoint = f"bulk_pdc_{frappe.generate_hash(length=8)}"
        frappe.db.savepoint(savepoint)
        try:
            payment_result = record_partial_payment(
                installment_name=installment_name,
                amount=pay_amount,
                mode_of_payment=mode_of_payment,
                payment_date=row.get("cheque_date") or nowdate(),
                remarks=f"Bulk PDC entry, cheque {row.get('cheque_no') or ''}".strip(),
            )
            payment_entry = None
            if payment_result.get("installments_paid"):
                payment_entry = payment_result["installments_paid"][0]["payment_entry"]

            pdc_name = None
            if row.get("cheque_no"):
                pdc = create_pdc(
                    tenant=row.get("tenant"),
                    cheque_no=row.get("cheque_no"),
                    bank=row.get("bank"),
                    cheque_date=row.get("cheque_date") or nowdate(),
                    amount=pay_amount,
                    lease_contract=row.get("lease_contract"),
                    company=company,
                    status="Cleared",
                    payment_entry=payment_entry,
                )
                pdc_name = pdc["name"]

            results.append({
                "rent_installment": installment_name,
                "status": "Paid",
                "payment_entry": payment_entry,
                "pdc": pdc_name,
            })
        except Exception:
            frappe.db.rollback(save_point=savepoint)
            frappe.log_error(title=f"Bulk PDC payment failed for {installment_name}", message=frappe.get_traceback())
            results.append({"rent_installment": installment_name, "status": "Failed", "error": "See Error Log"})

    return results


# ─────────────────────────────────────────────
# PURCHASE INVOICE — LANDLORD/EXPENSE LINKAGE
# ─────────────────────────────────────────────
PI_EXPENSE_ACCOUNT_MAP = {
    "Maintenance": "Repairs and Maintenance",
    "Utilities": "Utilities",
    "Municipality Fee": "Rates and Taxes",
    "Insurance": "Insurance",
    "Staff": "Staff Welfare",
}


def _resolve_expense_account(expense_type, company):
    account_name = PI_EXPENSE_ACCOUNT_MAP.get(expense_type)
    account = None
    if account_name:
        account = frappe.db.get_value("Account", {"account_name": account_name, "company": company})
    if not account:
        account = frappe.db.get_value("Company", company, "default_expense_account")
    return account


@frappe.whitelist()
def get_purchase_invoices_list(property=None):
    filters = {}
    if property:
        filters["custom_property"] = property
    return frappe.get_all(
        "Purchase Invoice",
        filters=filters,
        fields=[
            "name", "supplier", "posting_date", "grand_total", "status", "docstatus",
            "custom_property", "custom_tenancy_id", "custom_sales_invoice_id", "custom_loan",
        ],
        order_by="posting_date desc",
        limit_page_length=200,
    )


@frappe.whitelist()
def get_suppliers_list():
    return frappe.get_all("Supplier", fields=["name", "supplier_name"], order_by="supplier_name asc", limit_page_length=500)


@frappe.whitelist()
def create_purchase_invoice(supplier, property, amount, expense_type=None, description=None,
                             posting_date=None, tenancy=None, sales_invoice=None, loan=0, company=None):
    amount = flt(amount)
    if amount <= 0:
        frappe.throw("Amount must be greater than zero.")
    if not company:
        company = frappe.db.get_value("Property", property, "company")
    if not company:
        frappe.throw("Could not resolve Company from Property.")

    expense_account = _resolve_expense_account(expense_type, company)
    if not expense_account:
        frappe.throw(f"No expense account resolved for company {company}. Set a Default Expense Account.")

    doc = frappe.new_doc("Purchase Invoice")
    doc.supplier = supplier
    doc.company = company
    doc.posting_date = posting_date or nowdate()
    doc.custom_property = property
    doc.custom_tenancy_id = tenancy
    doc.custom_sales_invoice_id = sales_invoice
    doc.custom_loan = flt(loan)
    doc.append("items", {
        "item_name": description or expense_type or "Expense",
        "description": description or expense_type or "Expense",
        "qty": 1,
        "uom": "Nos",
        "rate": amount,
        "amount": amount,
        "expense_account": expense_account,
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name}


# ─────────────────────────────────────────────
# EXPENSE PROPERTY
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_expense_properties_list(property=None):
    filters = {}
    if property:
        filters["property"] = property
    return frappe.get_all(
        "Expense Property",
        filters=filters,
        fields=[
            "name", "property", "expense_date", "expense_type", "amount",
            "paid_amount", "outstanding_amount", "status", "docstatus", "description",
        ],
        order_by="expense_date desc",
        limit_page_length=200,
    )


@frappe.whitelist()
def create_expense_property(property, expense_type, amount, supplier, description=None, expense_date=None, company=None):
    amount = flt(amount)
    if amount <= 0:
        frappe.throw("Amount must be greater than zero.")
    if not company:
        company = frappe.db.get_value("Property", property, "company")

    doc = frappe.new_doc("Expense Property")
    doc.property = property
    doc.supplier = supplier
    doc.company = company
    doc.expense_type = expense_type
    doc.amount = amount
    doc.description = description
    doc.expense_date = expense_date or nowdate()
    doc.insert(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def submit_expense_property(name):
    doc = frappe.get_doc("Expense Property", name)
    doc.submit()
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def record_expense_partial_payment(expense_property, paid_amount, payment_date=None, remarks=None):
    from re_core.re_core.doctype.expense_property.expense_property import record_partial_payment as _record_expense_payment
    return _record_expense_payment(
        expense_property=expense_property,
        paid_amount=paid_amount,
        payment_date=payment_date,
        remarks=remarks,
    )
