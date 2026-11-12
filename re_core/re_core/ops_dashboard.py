"""Data helpers for the Property Operations dashboards and reports.

Rent Installment is a child table of Rent Schedule, so every read here first resolves the
Rent Schedules the current user may see (``frappe.get_list`` applies role permissions, User
Permissions and the tenant row-level rule in ``re_core.permissions``) and only then reads
the installment rows belonging to those schedules.
"""

import frappe
from frappe.utils import add_months, date_diff, flt, formatdate, get_first_day, getdate, nowdate

# installment statuses that have been billed to the tenant (Pending = not yet invoiced)
BILLED_STATUSES = ["Invoiced", "Partially Paid", "Paid", "Overdue", "Bounced"]
# installment statuses that can still carry an unpaid balance
UNPAID_STATUSES = ["Pending", "Invoiced", "Partially Paid", "Overdue", "Bounced"]

INSTALLMENT_FIELDS = ["name", "parent", "installment_no", "due_date", "amount", "paid_amount",
                      "outstanding_amount", "status"]


def permitted_schedules(company=None, tenant=None):
    """Return {rent_schedule_name: row} for schedules visible to the current user."""
    filters = {"status": ["!=", "Cancelled"]}
    if company:
        filters["company"] = company
    if tenant:
        filters["tenant"] = tenant
    rows = frappe.get_list("Rent Schedule", filters=filters,
                           fields=["name", "tenant", "lease_contract", "company"],
                           limit_page_length=0)
    return {r.name: r for r in rows}


def installments(schedule_names, extra_filters=None):
    if not schedule_names:
        return []
    filters = [["parenttype", "=", "Rent Schedule"], ["parent", "in", list(schedule_names)]]
    filters += extra_filters or []
    return frappe.get_all("Rent Installment", filters=filters, fields=INSTALLMENT_FIELDS,
                          order_by="due_date asc", limit_page_length=0)


def unpaid_balance(row):
    """Outstanding balance of an installment (falls back to amount - paid when not yet computed)."""
    return flt(row.outstanding_amount) or (flt(row.amount) - flt(row.paid_amount))


def _month_key(d):
    d = getdate(d)
    return (d.year, d.month)


def _month_label(key):
    return formatdate(f"{key[0]}-{key[1]:02d}-01", "MMM yyyy")


def _month_range(first_day, count):
    keys, cur = [], getdate(first_day)
    for _ in range(count):
        keys.append((cur.year, cur.month))
        cur = add_months(cur, 1)
    return keys


# --------------------------------------------------------------------------- charts

def billed_vs_collected_chart(company=None, months=12):
    """Rent billed vs collected per due-date month, trailing ``months`` months."""
    start = add_months(get_first_day(nowdate()), -(months - 1))
    keys = _month_range(start, months)
    billed = dict.fromkeys(keys, 0.0)
    collected = dict.fromkeys(keys, 0.0)
    sched = permitted_schedules(company)
    rows = installments(sched.keys(), [["due_date", ">=", start],
                                       ["status", "in", BILLED_STATUSES]])
    for r in rows:
        k = _month_key(r.due_date)
        if k in billed:
            billed[k] += flt(r.amount)
            collected[k] += flt(r.paid_amount)
    return {"labels": [_month_label(k) for k in keys],
            "datasets": [{"name": "Billed", "values": [round(billed[k], 3) for k in keys]},
                         {"name": "Collected", "values": [round(collected[k], 3) for k in keys]}]}


AGEING_BUCKETS = [("1-30 days", 1, 30), ("31-60 days", 31, 60), ("61-90 days", 61, 90), ("90+ days", 91, None)]


def ageing_bucket(days_overdue):
    for label, lo, hi in AGEING_BUCKETS:
        if days_overdue >= lo and (hi is None or days_overdue <= hi):
            return label
    return None


def arrears_ageing_chart(company=None):
    """Unpaid rent past its due date, grouped by days overdue."""
    today = getdate(nowdate())
    totals = {label: 0.0 for label, _, _ in AGEING_BUCKETS}
    sched = permitted_schedules(company)
    rows = installments(sched.keys(), [["due_date", "<", today],
                                       ["status", "in", UNPAID_STATUSES]])
    for r in rows:
        bal = unpaid_balance(r)
        if bal <= 0:
            continue
        bucket = ageing_bucket(date_diff(today, r.due_date))
        if bucket:
            totals[bucket] += bal
    return {"labels": list(totals), "datasets": [{"name": "Outstanding", "values": [round(v, 3) for v in totals.values()]}]}


def lease_expirations_chart(company=None, months=12):
    """Active / expiring leases ending in each of the next ``months`` months."""
    first = get_first_day(nowdate())
    keys = _month_range(first, months)
    counts = dict.fromkeys(keys, 0)
    filters = [["docstatus", "=", 1], ["status", "in", ["Active", "Expiring"]],
               ["end_date", ">=", first], ["end_date", "<", add_months(first, months)]]
    if company:
        filters.append(["company", "=", company])
    for r in frappe.get_list("Lease Contract", filters=filters, fields=["end_date"], limit_page_length=0):
        k = _month_key(r.end_date)
        if k in counts:
            counts[k] += 1
    return {"labels": [_month_label(k) for k in keys], "datasets": [{"name": "Leases ending", "values": [counts[k] for k in keys]}]}
