import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = [["docstatus", "=", 1]]
	for f in ("company", "tenant", "status"):
		if filters.get(f):
			conditions.append([f, "=", filters.get(f)])
	if filters.from_date:
		conditions.append(["cheque_date", ">=", filters.from_date])
	if filters.to_date:
		conditions.append(["cheque_date", "<=", filters.to_date])

	data = frappe.get_list(
		"Post Dated Cheque",
		filters=conditions,
		fields=["name", "cheque_no", "tenant", "lease_contract", "company", "cheque_date", "amount",
		        "status", "deposit_date", "clearance_date", "payment_entry"],
		order_by="cheque_date asc",
		limit_page_length=0,
	)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("PDC"), "fieldname": "name", "fieldtype": "Link", "options": "Post Dated Cheque", "width": 120},
		{"label": _("Cheque No"), "fieldname": "cheque_no", "fieldtype": "Data", "width": 110},
		{"label": _("Tenant"), "fieldname": "tenant", "fieldtype": "Link", "options": "Tenant", "width": 130},
		{"label": _("Lease"), "fieldname": "lease_contract", "fieldtype": "Link", "options": "Lease Contract", "width": 150},
		{"label": _("Cheque Date"), "fieldname": "cheque_date", "fieldtype": "Date", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Deposited"), "fieldname": "deposit_date", "fieldtype": "Date", "width": 100},
		{"label": _("Cleared"), "fieldname": "clearance_date", "fieldtype": "Date", "width": 100},
		{"label": _("Payment Entry"), "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 140},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 130},
	]
