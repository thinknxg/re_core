import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	today = getdate(nowdate())
	horizon = add_days(today, cint(filters.days_ahead) or 90)
	conditions = [["docstatus", "=", 1], ["status", "in", ["Active", "Expiring"]], ["end_date", "<=", horizon]]
	for f in ("company", "property", "tenant"):
		if filters.get(f):
			conditions.append([f, "=", filters.get(f)])

	data = frappe.get_list(
		"Lease Contract",
		filters=conditions,
		fields=["name", "tenant", "property", "unit", "company", "start_date", "end_date", "status",
		        "auto_renew", "total_contract_value"],
		order_by="end_date asc",
		limit_page_length=0,
	)
	for row in data:
		row["days_left"] = date_diff(row.end_date, today)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Lease"), "fieldname": "name", "fieldtype": "Link", "options": "Lease Contract", "width": 150},
		{"label": _("Tenant"), "fieldname": "tenant", "fieldtype": "Link", "options": "Tenant", "width": 130},
		{"label": _("Property"), "fieldname": "property", "fieldtype": "Link", "options": "Property", "width": 130},
		{"label": _("Unit"), "fieldname": "unit", "fieldtype": "Link", "options": "Unit", "width": 110},
		{"label": _("Start"), "fieldname": "start_date", "fieldtype": "Date", "width": 100},
		{"label": _("End"), "fieldname": "end_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Auto Renew"), "fieldname": "auto_renew", "fieldtype": "Check", "width": 90},
		{"label": _("Contract Value"), "fieldname": "total_contract_value", "fieldtype": "Currency", "width": 130},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 130},
	]
