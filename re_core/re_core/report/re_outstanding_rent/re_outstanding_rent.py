import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from re_core.re_core.ops_dashboard import (
	UNPAID_STATUSES,
	ageing_bucket,
	installments,
	permitted_schedules,
	unpaid_balance,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	today = getdate(nowdate())
	sched = permitted_schedules(filters.company, filters.tenant)
	extra = [["status", "in", UNPAID_STATUSES], ["due_date", "<=", filters.as_on_date or today]]
	if filters.from_date:
		extra.append(["due_date", ">=", filters.from_date])

	data = []
	for r in installments(sched.keys(), extra):
		balance = unpaid_balance(r)
		if balance <= 0:
			continue
		days = max(date_diff(filters.as_on_date or today, r.due_date), 0)
		s = sched[r.parent]
		data.append({
			"rent_schedule": r.parent,
			"lease_contract": s.lease_contract,
			"tenant": s.tenant,
			"company": s.company,
			"installment_no": r.installment_no,
			"due_date": r.due_date,
			"amount": flt(r.amount),
			"paid_amount": flt(r.paid_amount),
			"outstanding": balance,
			"days_overdue": days,
			"ageing": ageing_bucket(days) if days else _("Current"),
			"status": r.status,
		})
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Rent Schedule"), "fieldname": "rent_schedule", "fieldtype": "Link", "options": "Rent Schedule", "width": 130},
		{"label": _("Lease"), "fieldname": "lease_contract", "fieldtype": "Link", "options": "Lease Contract", "width": 150},
		{"label": _("Tenant"), "fieldname": "tenant", "fieldtype": "Link", "options": "Tenant", "width": 130},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 130},
		{"label": _("Inst. #"), "fieldname": "installment_no", "fieldtype": "Int", "width": 70},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 120},
		{"label": _("Days Overdue"), "fieldname": "days_overdue", "fieldtype": "Int", "width": 100},
		{"label": _("Ageing"), "fieldname": "ageing", "fieldtype": "Data", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
	]
