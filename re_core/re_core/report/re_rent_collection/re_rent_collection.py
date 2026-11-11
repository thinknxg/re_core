import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, getdate, nowdate

from re_core.re_core.ops_dashboard import BILLED_STATUSES, installments, permitted_schedules


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.from_date or add_months(get_first_day(nowdate()), -11))
	to_date = getdate(filters.to_date or nowdate())
	sched = permitted_schedules(filters.company)
	rows = installments(sched.keys(), [["due_date", ">=", from_date], ["due_date", "<=", to_date],
	                                   ["status", "in", BILLED_STATUSES]])
	months = {}
	for r in rows:
		d = getdate(r.due_date)
		m = months.setdefault((d.year, d.month), {"billed": 0.0, "collected": 0.0})
		m["billed"] += flt(r.amount)
		m["collected"] += flt(r.paid_amount)

	data = []
	for (y, mo), v in sorted(months.items()):
		outstanding = v["billed"] - v["collected"]
		data.append({
			"month": f"{y}-{mo:02d}",
			"billed": v["billed"],
			"collected": v["collected"],
			"outstanding": outstanding,
			"collection_pct": (v["collected"] / v["billed"] * 100) if v["billed"] else 0,
		})
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Month (by due date)"), "fieldname": "month", "fieldtype": "Data", "width": 150},
		{"label": _("Billed"), "fieldname": "billed", "fieldtype": "Currency", "width": 130},
		{"label": _("Collected"), "fieldname": "collected", "fieldtype": "Currency", "width": 130},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 130},
		{"label": _("Collection %"), "fieldname": "collection_pct", "fieldtype": "Percent", "width": 120},
	]
