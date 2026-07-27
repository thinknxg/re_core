"""
re_core/re_core/tenant_portal_api.py

Tenant-facing portal API. Kept in its OWN module (not appended to api.py,
and NOT a package folder — remember the api/ vs api.py precedence bug from
earlier) so the existing endpoint surface in api.py is untouched.

Copy this file to:
    apps/re_core/re_core/re_core/tenant_portal_api.py

Every tenant-facing whitelisted method takes `token` and resolves the
tenant server-side via resolve_tenant_from_token(). NEVER trust a `tenant`
param passed from the client for scoping — there is no real Frappe session
backing this, so the token is the only trust boundary.

Validate before deploying:
    python3 -c "import ast; ast.parse(open('tenant_portal_api.py').read())"
"""

import secrets
from datetime import datetime, timedelta

import frappe
from frappe.utils import flt, nowdate, now_datetime

# Reuse existing payment logic rather than duplicating it
from re_core.re_core.api import record_partial_payment  # noqa: F401

SESSION_LIFETIME_DAYS = 7


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def tenant_portal_login(mobile, access_code):
    """Validate mobile + access code, issue an opaque session token."""
    if not mobile or not access_code:
        frappe.throw("Mobile number and access code are required", frappe.AuthenticationError)

    tenant_name = frappe.db.get_value("Tenant", {"mobile": mobile}, "name")
    if not tenant_name:
        # Same error for "no such tenant" and "wrong code" — don't leak which one
        frappe.throw("Invalid mobile number or access code", frappe.AuthenticationError)

    tenant_doc = frappe.get_doc("Tenant", tenant_name)

    stored_code = tenant_doc.get_password("portal_access_code", raise_exception=False)
    if not stored_code or stored_code != access_code:
        frappe.throw("Invalid mobile number or access code", frappe.AuthenticationError)

    if not tenant_doc.enable_portal:
        frappe.throw("Portal access is disabled for this account. Contact your property manager.")

    token = secrets.token_urlsafe(32)
    expiry = now_datetime() + timedelta(days=SESSION_LIFETIME_DAYS)

    frappe.get_doc({
        "doctype": "Tenant Portal Session",
        "tenant": tenant_name,
        "token": token,
        "expiry": expiry,
        "created_on": now_datetime(),
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "token": token,
        "tenant": tenant_name,
        "tenant_name": tenant_doc.get("tenant_name") or tenant_doc.get("full_name") or tenant_name,
        "expiry": str(expiry),
    }


@frappe.whitelist(allow_guest=True)
def tenant_portal_logout(token):
    frappe.db.delete("Tenant Portal Session", {"token": token})
    frappe.db.commit()
    return {"success": True}


def resolve_tenant_from_token(token):
    """Call at the top of every tenant-facing endpoint. Returns tenant name or throws."""
    if not token:
        frappe.throw("Missing session token", frappe.AuthenticationError)

    session = frappe.db.get_value(
        "Tenant Portal Session", {"token": token}, ["name", "tenant", "expiry"], as_dict=True
    )
    if not session:
        frappe.throw("Invalid or expired session. Please log in again.", frappe.AuthenticationError)

    if session.expiry < now_datetime():
        frappe.db.delete("Tenant Portal Session", {"name": session.name})
        frappe.db.commit()
        frappe.throw("Session expired. Please log in again.", frappe.AuthenticationError)

    frappe.db.set_value("Tenant Portal Session", session.name, "last_used_on", now_datetime())
    return session.tenant


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def tenant_portal_dashboard(token):
    tenant = resolve_tenant_from_token(token)

    leases = frappe.get_all(
        "Lease Contract",
        filters={"tenant": tenant, "status": ["in", ["Active", "active"]]},
        fields=["name", "unit", "property", "start_date", "end_date"],
    )

    lease_names = [l.name for l in leases]
    next_due = None
    total_outstanding = 0

    if lease_names:
        schedules = frappe.get_all(
            "Rent Schedule", filters={"lease_contract": ["in", lease_names]}, fields=["name"]
        )
        schedule_names = [s.name for s in schedules]

        if schedule_names:
            installments = frappe.get_all(
                "Rent Installment",
                filters={"parent": ["in", schedule_names], "status": ["!=", "Paid"]},
                fields=["name", "due_date", "amount", "paid_amount", "outstanding_amount", "status"],
                order_by="due_date asc",
            )
            if installments:
                next_due = installments[0]
                total_outstanding = sum(flt(i.outstanding_amount) for i in installments)

    open_maintenance = frappe.db.count(
        "Maintenance Request",
        {"tenant": tenant, "status": ["not in", ["Completed", "Rejected", "Cancelled"]]},
    )

    return {
        "leases": leases,
        "next_due_installment": next_due,
        "total_outstanding": total_outstanding,
        "open_maintenance_requests": open_maintenance,
    }


# ---------------------------------------------------------------------
# My Lease
# ---------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def tenant_portal_lease(token):
    tenant = resolve_tenant_from_token(token)

    leases = frappe.get_all(
        "Lease Contract",
        filters={"tenant": tenant},
        fields=[
            "name", "title", "unit", "property", "owner_ref", "company",
            "start_date", "end_date", "duration_months", "status",
            "total_contract_value", "payment_frequency",
            "security_deposit_amount", "rent_schedule",
        ],
        order_by="start_date desc",
    )
    return {"leases": leases}


# ---------------------------------------------------------------------
# Payments / Installments
# ---------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def tenant_portal_installments(token):
    tenant = resolve_tenant_from_token(token)

    leases = frappe.get_all("Lease Contract", filters={"tenant": tenant}, fields=["name"])
    lease_names = [l.name for l in leases]
    if not lease_names:
        return {"installments": []}

    schedules = frappe.get_all(
        "Rent Schedule", filters={"lease_contract": ["in", lease_names]}, fields=["name", "lease_contract"]
    )
    schedule_names = [s.name for s in schedules]
    if not schedule_names:
        return {"installments": []}

    installments = frappe.get_all(
        "Rent Installment",
        filters={"parent": ["in", schedule_names]},
        fields=[
            "name", "parent", "installment_no", "due_date", "amount",
            "paid_amount", "outstanding_amount", "status", "sales_invoice", "pdc",
        ],
        order_by="due_date asc",
    )
    return {"installments": installments}


@frappe.whitelist(allow_guest=True)
def tenant_portal_pay_installment(token, installment_name, amount, mode_of_payment="Cash", remarks=None):
    """Scoped wrapper around the existing record_partial_payment — verifies
    the installment actually belongs to the resolved tenant before calling."""
    tenant = resolve_tenant_from_token(token)

    schedule_name = frappe.db.get_value("Rent Installment", installment_name, "parent")
    if not schedule_name:
        frappe.throw("Installment not found")

    lease_contract, sched_tenant = frappe.db.get_value(
        "Rent Schedule", schedule_name, ["lease_contract", "tenant"]
    )

    # belt-and-braces: check both Rent Schedule.tenant and the Lease Contract's tenant
    lease_tenant = frappe.db.get_value("Lease Contract", lease_contract, "tenant") if lease_contract else None

    if tenant not in (sched_tenant, lease_tenant):
        frappe.throw("Not authorized to pay this installment", frappe.PermissionError)

    return record_partial_payment(
        installment_name=installment_name,
        amount=amount,
        mode_of_payment=mode_of_payment,
        payment_date=nowdate(),
        remarks=remarks,
    )


# ---------------------------------------------------------------------
# Cheque Schedule (PDCs)
# ---------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def tenant_portal_pdcs(token):
    tenant = resolve_tenant_from_token(token)

    pdcs = frappe.get_all(
        "Post Dated Cheque",
        filters={"tenant": tenant},
        fields=[
            "name", "cheque_no", "bank", "cheque_date", "amount",
            "status", "deposit_date", "clearance_date", "lease_contract",
        ],
        order_by="cheque_date asc",
    )
    return {"cheques": pdcs}


# ---------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------
# Matches the real Maintenance Request schema: linked via `unit` (not
# lease_contract — that field doesn't exist on this doctype), `property`
# is auto-fetched from unit, `tenant` is set here on portal-raised
# requests, category options are "\nPlumbing\nElectrical\nAC\nCivil\n
# Appliances\nPest Control\nOther", priority is Low/Medium/High/Emergency,
# status is Open/In Progress/On Hold/Completed/Rejected/Cancelled.
# Resolution (maintenance_job, resolution_notes) is staff-only — never
# exposed for tenant write access.

@frappe.whitelist(allow_guest=True)
def tenant_portal_maintenance_list(token):
    tenant = resolve_tenant_from_token(token)

    requests = frappe.get_all(
        "Maintenance Request",
        filters={"tenant": tenant},
        fields=[
            "name", "unit", "property", "category", "priority",
            "description", "status", "maintenance_job", "resolution_notes",
            "creation", "modified",
        ],
        order_by="creation desc",
    )
    return {"requests": requests}


def _tenant_units(tenant):
    """Units the tenant currently holds an active lease on."""
    return frappe.get_all(
        "Lease Contract",
        filters={"tenant": tenant, "status": ["in", ["Active", "active"]]},
        pluck="unit",
    )


@frappe.whitelist(allow_guest=True)
def tenant_portal_create_maintenance_request(
    token, category, description, priority="Medium",
    unit=None, photo_1=None, photo_2=None
):
    tenant = resolve_tenant_from_token(token)
    tenant_units = _tenant_units(tenant)

    if not tenant_units:
        frappe.throw("No active lease found for this account")

    if not unit:
        unit = tenant_units[0]
    elif unit not in tenant_units:
        frappe.throw("Not authorized to raise a request against this unit", frappe.PermissionError)

    doc = frappe.get_doc({
        "doctype": "Maintenance Request",
        "unit": unit,
        "tenant": tenant,
        "category": category,
        "priority": priority,
        "description": description,
        "photo_1": photo_1,
        "photo_2": photo_2,
        "status": "Open",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name}


@frappe.whitelist(allow_guest=True)
def tenant_portal_units(token):
    """Helper for the New Request form — units the tenant can raise a request against."""
    tenant = resolve_tenant_from_token(token)
    units = _tenant_units(tenant)
    return {"units": units}


# ---------------------------------------------------------------------
# My Documents
# ---------------------------------------------------------------------
# NOTE: assumes documents are Frappe File attachments on Lease Contract.
# If there's a dedicated "Tenant Document" doctype instead, swap the
# frappe.get_all("File", ...) block below to query that doctype.

@frappe.whitelist(allow_guest=True)
def tenant_portal_documents(token):
    tenant = resolve_tenant_from_token(token)

    leases = frappe.get_all("Lease Contract", filters={"tenant": tenant}, fields=["name"])
    lease_names = [l.name for l in leases]
    if not lease_names:
        return {"documents": []}

    files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Lease Contract", "attached_to_name": ["in", lease_names]},
        fields=["name", "file_name", "file_url", "attached_to_name", "creation"],
        order_by="creation desc",
    )
    return {"documents": files}
