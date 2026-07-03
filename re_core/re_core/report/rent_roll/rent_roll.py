# Rent Roll: unit x lease x installment matrix with occupancy and collection position.
import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)
    return columns, data, None, None, summary


def get_columns():
    return [
        {"label": _("Property"), "fieldname": "property", "fieldtype": "Link",
         "options": "Property", "width": 150},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Link",
         "options": "Unit", "width": 110},
        {"label": _("Type"), "fieldname": "unit_type", "fieldtype": "Data", "width": 80},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": _("Tenant"), "fieldname": "tenant_name", "fieldtype": "Data", "width": 150},
        {"label": _("Lease"), "fieldname": "lease", "fieldtype": "Link",
         "options": "Lease Contract", "width": 130},
        {"label": _("Start"), "fieldname": "start_date", "fieldtype": "Date", "width": 95},
        {"label": _("End"), "fieldname": "end_date", "fieldtype": "Date", "width": 95},
        {"label": _("Contract Value"), "fieldname": "contract_value",
         "fieldtype": "Currency", "width": 120},
        {"label": _("Collected"), "fieldname": "collected", "fieldtype": "Currency", "width": 110},
        {"label": _("Overdue"), "fieldname": "overdue", "fieldtype": "Currency", "width": 110},
        {"label": _("Next Due"), "fieldname": "next_due", "fieldtype": "Date", "width": 95},
    ]


def get_data(filters):
    conditions = ["1=1"]
    values = {}
    if filters.get("company"):
        conditions.append("u.company = %(company)s")
        values["company"] = filters.company
    if filters.get("property"):
        conditions.append("u.property = %(property)s")
        values["property"] = filters.property
    if filters.get("status"):
        conditions.append("u.status = %(status)s")
        values["status"] = filters.status

    rows = frappe.db.sql(f"""
        SELECT u.property, u.name AS unit, u.unit_type, u.status,
               lc.name AS lease, lc.tenant_name, lc.start_date, lc.end_date,
               lc.total_contract_value AS contract_value, lc.rent_schedule
        FROM `tabUnit` u
        LEFT JOIN `tabLease Contract` lc
               ON lc.name = u.current_lease AND lc.docstatus = 1
        WHERE {' AND '.join(conditions)}
        ORDER BY u.property, u.unit_no
    """, values, as_dict=True)

    for row in rows:
        row.collected = row.overdue = 0
        row.next_due = None
        if not row.rent_schedule:
            continue
        installments = frappe.get_all(
            "Rent Installment", filters={"parent": row.rent_schedule},
            fields=["amount", "status", "due_date"], order_by="due_date asc")
        for inst in installments:
            if inst.status == "Paid":
                row.collected += flt(inst.amount)
            elif inst.status in ("Overdue", "Bounced"):
                row.overdue += flt(inst.amount)
            if inst.status in ("Pending", "Invoiced", "Overdue") and not row.next_due:
                row.next_due = inst.due_date
    return rows


def get_summary(data):
    total = len(data)
    occupied = len([d for d in data if d.status == "Occupied"])
    overdue = sum(flt(d.overdue) for d in data)
    return [
        {"label": _("Units"), "value": total, "datatype": "Int"},
        {"label": _("Occupancy"), "datatype": "Percent",
         "value": flt(occupied * 100 / total, 1) if total else 0},
        {"label": _("Total Overdue"), "value": overdue, "datatype": "Currency",
         "indicator": "Red" if overdue else "Green"},
    ]
