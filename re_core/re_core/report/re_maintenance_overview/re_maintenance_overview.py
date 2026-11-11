import frappe
from frappe import _
from frappe.utils import date_diff, getdate, nowdate

OPEN_STATUSES = ["Open", "In Progress", "On Hold"]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = []
	if filters.status:
		conditions.append(["status", "=", filters.status])
	elif filters.open_only:
		conditions.append(["status", "in", OPEN_STATUSES])
	for f in ("property", "category", "priority"):
		if filters.get(f):
			conditions.append([f, "=", filters.get(f)])

	data = frappe.get_list(
		"Maintenance Request",
		filters=conditions,
		fields=["name", "property", "unit", "tenant", "category", "priority", "status", "maintenance_job",
		        "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)
	today = getdate(nowdate())
	for row in data:
		row["age_days"] = date_diff(today, getdate(row.creation))
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Request"), "fieldname": "name", "fieldtype": "Link", "options": "Maintenance Request", "width": 140},
		{"label": _("Property"), "fieldname": "property", "fieldtype": "Link", "options": "Property", "width": 130},
		{"label": _("Unit"), "fieldname": "unit", "fieldtype": "Link", "options": "Unit", "width": 110},
		{"label": _("Tenant"), "fieldname": "tenant", "fieldtype": "Link", "options": "Tenant", "width": 130},
		{"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 100},
		{"label": _("Priority"), "fieldname": "priority", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Age (days)"), "fieldname": "age_days", "fieldtype": "Int", "width": 90},
		{"label": _("Job"), "fieldname": "maintenance_job", "fieldtype": "Link", "options": "Maintenance Job", "width": 120},
	]
