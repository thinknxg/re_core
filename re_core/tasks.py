"""Scheduled jobs for re_core (wired in hooks.scheduler_events)."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate


# ------------------------------------------------------------------ invoicing

def invoice_due_installments():
    """Create Sales Invoices for Pending installments due within the lead window."""
    settings = frappe.get_single("Property Settings")
    if not settings.rent_item:
        return
    horizon = add_days(nowdate(), int(settings.invoice_lead_days or 7))
    rows = frappe.db.sql(
        """
        SELECT ri.name, ri.parent, ri.due_date, ri.amount, rs.lease_contract
        FROM `tabRent Installment` ri
        JOIN `tabRent Schedule` rs ON rs.name = ri.parent
        WHERE ri.status = 'Pending' AND ri.due_date <= %s AND rs.status = 'Active'
        """, horizon, as_dict=True)

    for row in rows:
        try:
            _invoice_installment(row, settings)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="re_core: installment invoicing failed",
                             message=f"Installment {row.name} / lease {row.lease_contract}")


def _invoice_installment(row, settings):
    lease = frappe.get_doc("Lease Contract", row.lease_contract)
    if lease.status not in ("Active", "Expiring"):
        return
    customer = frappe.db.get_value("Tenant", lease.tenant, "customer")
    if not customer:
        return

    si = frappe.new_doc("Sales Invoice")
    si.customer = customer
    si.company = lease.company
    si.due_date = max(getdate(row.due_date), getdate(nowdate()))
    tax_template = _dominant_tax_template(lease)
    si.append("items", {
        "item_code": settings.rent_item,
        "item_name": _("Rent installment {0}").format(row.due_date),
        "description": _("Lease {0} — installment due {1}").format(lease.name, row.due_date),
        "qty": 1,
        "rate": flt(row.amount),
        "item_tax_template": tax_template,
    })
    si.insert(ignore_permissions=True)
    si.submit()
    frappe.db.set_value("Rent Installment", row.name,
                        {"sales_invoice": si.name, "status": "Invoiced"})


def _dominant_tax_template(lease):
    """Use the tax template of the largest charge row (Oman residential rent: blank = exempt)."""
    best, template = 0, None
    for charge in lease.charges:
        if flt(charge.amount) > best:
            best, template = flt(charge.amount), charge.item_tax_template
    return template


def mark_overdue_installments():
    grace = int(frappe.db.get_single_value("Property Settings", "overdue_grace_days") or 0)
    cutoff = add_days(nowdate(), -grace)
    for row in frappe.get_all("Rent Installment",
                              filters={"status": ["in", ["Pending", "Invoiced"]],
                                       "due_date": ["<", cutoff]},
                              fields=["name", "parent"]):
        frappe.db.set_value("Rent Installment", row.name, "status", "Overdue")


# ------------------------------------------------------------------ lease expiry

def lease_expiry_pipeline():
    settings = frappe.get_single("Property Settings")
    today = getdate(nowdate())

    # Active -> Expiring
    flag_from = add_days(today, int(settings.expiring_flag_days or 90))
    for name in frappe.get_all("Lease Contract",
                               filters={"docstatus": 1, "status": "Active",
                                        "end_date": ["<=", flag_from]},
                               pluck="name"):
        frappe.db.set_value("Lease Contract", name, "status", "Expiring")

    # Renewal ToDo
    todo_from = add_days(today, int(settings.renewal_todo_days or 60))
    for lease in frappe.get_all("Lease Contract",
                                filters={"docstatus": 1, "status": "Expiring",
                                         "end_date": ["<=", todo_from]},
                                fields=["name", "tenant_name", "end_date", "owner"]):
        if not frappe.db.exists("ToDo", {"reference_type": "Lease Contract",
                                         "reference_name": lease.name, "status": "Open"}):
            frappe.get_doc({
                "doctype": "ToDo",
                "reference_type": "Lease Contract",
                "reference_name": lease.name,
                "allocated_to": lease.owner,
                "date": lease.end_date,
                "description": _("Renewal follow-up: lease {0} ({1}) ends {2}").format(
                    lease.name, lease.tenant_name, lease.end_date),
            }).insert(ignore_permissions=True)

    # Expiring -> Expired, free the unit
    for lease in frappe.get_all("Lease Contract",
                                filters={"docstatus": 1,
                                         "status": ["in", ["Active", "Expiring"]],
                                         "end_date": ["<", today]},
                                fields=["name", "unit"]):
        frappe.db.set_value("Lease Contract", lease.name, "status", "Expired")
        frappe.db.set_value("Unit", lease.unit, {"status": "Vacant", "current_lease": None})


# ------------------------------------------------------------------ PDCs

def pdc_deposit_reminders():
    horizon = add_days(nowdate(), 3)
    due = frappe.get_all("Post Dated Cheque",
                         filters={"docstatus": 1, "status": "Received",
                                  "cheque_date": ["<=", horizon]},
                         fields=["name", "cheque_no", "tenant", "amount", "cheque_date"])
    if not due:
        return
    users = [u for u in frappe.get_all(
        "Has Role", filters={"role": "Accounts User", "parenttype": "User"}, pluck="parent")
        if frappe.db.get_value("User", u, "enabled")]
    for pdc in due:
        for user in users:
            frappe.get_doc({
                "doctype": "Notification Log",
                "for_user": user,
                "type": "Alert",
                "document_type": "Post Dated Cheque",
                "document_name": pdc.name,
                "subject": _("PDC {0} ({1}) due for deposit on {2}").format(
                    pdc.cheque_no, pdc.tenant, pdc.cheque_date),
            }).insert(ignore_permissions=True)
