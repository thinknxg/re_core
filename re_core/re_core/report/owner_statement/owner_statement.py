# Owner Statement (invoiced basis): rent income invoiced in the period, owner-billable
# maintenance expenses, management fee, and the resulting net payable to the owner.
import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.get("property_owner"):
        frappe.throw(_("Please select a Property Owner."))
    if not (filters.get("from_date") and filters.get("to_date")):
        frappe.throw(_("Please set the statement period."))

    owner = frappe.db.get_value(
        "Property Owner", filters.property_owner,
        ["owner_name", "company", "management_fee_percent"], as_dict=True)

    columns = get_columns()
    data, gross_income, expenses = get_rows(filters, owner)
    fee = flt(gross_income * flt(owner.management_fee_percent) / 100, 3)
    net = flt(gross_income - expenses - fee, 3)

    summary = [
        {"label": _("Rent Invoiced"), "value": gross_income, "datatype": "Currency"},
        {"label": _("Owner Expenses"), "value": expenses, "datatype": "Currency"},
        {"label": _("Management Fee ({0}%)").format(owner.management_fee_percent),
         "value": fee, "datatype": "Currency"},
        {"label": _("Net Payable to Owner"), "value": net, "datatype": "Currency",
         "indicator": "Green" if net >= 0 else "Red"},
    ]
    message = _("Basis: rent invoices posted and owner-billable maintenance jobs "
                "completed between {0} and {1}, for {2}.").format(
        frappe.format(getdate(filters.from_date), {"fieldtype": "Date"}),
        frappe.format(getdate(filters.to_date), {"fieldtype": "Date"}),
        owner.owner_name)
    return columns, data, message, None, summary


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": _("Type"), "fieldname": "entry_type", "fieldtype": "Data", "width": 110},
        {"label": _("Reference"), "fieldname": "reference", "fieldtype": "Dynamic Link",
         "options": "reference_doctype", "width": 150},
        {"label": _("Ref DocType"), "fieldname": "reference_doctype",
         "fieldtype": "Data", "width": 110},
        {"label": _("Unit"), "fieldname": "unit", "fieldtype": "Link",
         "options": "Unit", "width": 110},
        {"label": _("Description"), "fieldname": "description", "fieldtype": "Data",
         "width": 240},
        {"label": _("Income"), "fieldname": "income", "fieldtype": "Currency", "width": 110},
        {"label": _("Expense"), "fieldname": "expense", "fieldtype": "Currency", "width": 110},
    ]


def get_rows(filters, owner):
    rows, gross, expenses = [], 0.0, 0.0

    # Income: rent Sales Invoices created from installments on this owner's leases
    invoices = frappe.db.sql("""
        SELECT si.name, si.posting_date, si.base_grand_total, ri.parent AS schedule,
               lc.unit, lc.tenant_name
        FROM `tabSales Invoice` si
        JOIN `tabRent Installment` ri ON ri.sales_invoice = si.name
        JOIN `tabRent Schedule` rs ON rs.name = ri.parent
        JOIN `tabLease Contract` lc ON lc.name = rs.lease_contract
        JOIN `tabProperty` p ON p.name = lc.property
        WHERE si.docstatus = 1 AND p.owner_ref = %(owner)s
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY si.posting_date
    """, {"owner": filters.property_owner, "from_date": filters.from_date,
          "to_date": filters.to_date}, as_dict=True)
    for inv in invoices:
        gross += flt(inv.base_grand_total)
        rows.append({
            "date": inv.posting_date, "entry_type": _("Rent Invoice"),
            "reference": inv.name, "reference_doctype": "Sales Invoice",
            "unit": inv.unit,
            "description": _("Rent — {0}").format(inv.tenant_name),
            "income": flt(inv.base_grand_total), "expense": 0,
        })

    # Expenses: completed maintenance jobs billable to the owner
    jobs = frappe.db.sql("""
        SELECT mj.name, mj.completion_date, mj.total_cost, mj.unit, mj.work_notes
        FROM `tabMaintenance Job` mj
        JOIN `tabUnit` u ON u.name = mj.unit
        JOIN `tabProperty` p ON p.name = u.property
        WHERE mj.docstatus = 1 AND mj.billable_to = 'Owner'
          AND p.owner_ref = %(owner)s
          AND mj.completion_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY mj.completion_date
    """, {"owner": filters.property_owner, "from_date": filters.from_date,
          "to_date": filters.to_date}, as_dict=True)
    for job in jobs:
        expenses += flt(job.total_cost)
        rows.append({
            "date": job.completion_date, "entry_type": _("Maintenance"),
            "reference": job.name, "reference_doctype": "Maintenance Job",
            "unit": job.unit,
            "description": job.work_notes or _("Maintenance job"),
            "income": 0, "expense": flt(job.total_cost),
        })

    rows.sort(key=lambda r: getdate(r["date"]))
    return rows, flt(gross, 3), flt(expenses, 3)
