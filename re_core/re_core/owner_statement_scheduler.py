import frappe
from frappe.utils import flt, getdate, get_first_day, get_last_day, add_months

from re_core.re_core.report.owner_statement.owner_statement import get_rows


def generate_monthly_owner_statements():
	"""Scheduled monthly: creates + submits an Owner Statement for every
	Property Owner with at least one Landlord-owned Property, for the
	previous full calendar month. Skips owners who already have a
	statement for that period (idempotent)."""

	today = getdate()
	period_from = get_first_day(add_months(today, -1))
	period_to = get_last_day(add_months(today, -1))

	owners = frappe.db.sql("""
		SELECT DISTINCT po.name
		FROM `tabProperty Owner` po
		JOIN `tabProperty` p ON p.owner_ref = po.name
		WHERE p.ownership_type = 'Landlord'
	""", as_dict=True)

	for row in owners:
		owner_name = row.name

		if frappe.db.exists("Owner Statement", {
			"property_owner": owner_name,
			"period_from": period_from,
			"period_to": period_to,
		}):
			continue  # already generated for this period

		_generate_statement_for_owner(owner_name, period_from, period_to)


def _generate_statement_for_owner(owner_name, period_from, period_to):
	owner = frappe.db.get_value(
		"Property Owner", owner_name,
		["owner_name", "company", "management_fee_percent"], as_dict=True)

	filters = frappe._dict({
		"property_owner": owner_name,
		"from_date": period_from,
		"to_date": period_to,
	})

	rows, gross_income, expenses = get_rows(filters, owner)

	if not rows:
		return  # nothing to statement this period

	# Fee precedence: Unit override -> Property override -> Property Owner flat %
	management_fee_total = 0.0
	onetime_commission_total = 0.0
	statement_lines = []
	charged_leases_this_run = set()

	for r in rows:
		line = dict(r)
		line["reference_doctype"] = r["reference_doctype"]
		line["reference"] = r["reference"]

		if r["entry_type"] == "Rent Invoice" and r.get("income"):
			fee_type, fee_value, onetime_commission = _get_fee_and_commission(r)

			if fee_type == "Percentage":
				line_fee = flt(r["income"]) * flt(fee_value) / 100
			else:
				line_fee = flt(fee_value)
			management_fee_total += line_fee

			lease_contract = _get_lease_contract_for_row(r)
			line["lease_contract"] = lease_contract

			if (
				lease_contract
				and lease_contract not in charged_leases_this_run
				and not _lease_already_statemented(lease_contract)
			):
				line["onetime_commission"] = flt(onetime_commission)
				onetime_commission_total += flt(onetime_commission)
				charged_leases_this_run.add(lease_contract)
			else:
				line["onetime_commission"] = 0

		statement_lines.append(line)

	net_payable = flt(gross_income) - flt(expenses) - flt(management_fee_total) - flt(onetime_commission_total)

	doc = frappe.get_doc({
		"doctype": "Owner Statement",
		"property_owner": owner_name,
		"company": owner.company,
		"period_from": period_from,
		"period_to": period_to,
		"rent_invoiced": gross_income,
		"management_fee": management_fee_total,
		"onetime_commission_deducted": onetime_commission_total,
		"owner_expenses": expenses,
		"net_payable": net_payable,
		"statement_lines": statement_lines,
	})
	doc.insert(ignore_permissions=True)
	doc.submit()


def _get_lease_contract_for_row(row):
	# Row comes from a Sales Invoice via Rent Installment -> Rent Schedule -> Lease Contract.
	# Reference is the Sales Invoice name; walk it back.
	installment = frappe.db.get_value(
		"Rent Installment", {"sales_invoice": row["reference"]}, "parent")
	if not installment:
		return None
	return frappe.db.get_value("Rent Schedule", installment, "lease_contract")


def _get_fee_and_commission(row):
	# onetime_commission is resolved independently of fee-type precedence:
	# Unit's value wins if set, else Property's - regardless of which fee
	# source (Unit/Property/Owner flat %) ends up being used for the fee itself.
	unit = frappe.db.get_value(
		"Unit", row.get("unit"),
		["management_fee_type", "management_fee_value", "onetime_commission"], as_dict=True
	) if row.get("unit") else None
	lease_contract = _get_lease_contract_for_row(row)
	property_name = frappe.db.get_value("Lease Contract", lease_contract, "property") if lease_contract else None
	prop = frappe.db.get_value(
		"Property", property_name,
		["management_fee_type", "management_fee_value", "onetime_commission"], as_dict=True
	) if property_name else None
	onetime_commission = flt(
		(unit.onetime_commission if unit and unit.onetime_commission else None)
		or (prop.onetime_commission if prop else 0)
	)
	if unit and unit.management_fee_value:
		return unit.management_fee_type, unit.management_fee_value, onetime_commission
	if prop and prop.management_fee_value:
		return prop.management_fee_type, prop.management_fee_value, onetime_commission
	# Fallback: Property Owner flat percentage for the fee, but onetime_commission
	# (resolved above) still applies if Unit/Property has one set.
	owner_ref = frappe.db.get_value("Property", property_name, "owner_ref") if property_name else None
	fee_percent = frappe.db.get_value("Property Owner", owner_ref, "management_fee_percent") if owner_ref else 0
	return "Percentage", flt(fee_percent), onetime_commission
def _lease_already_statemented(lease_contract):
	return frappe.db.exists("Owner Statement Line", {
		"lease_contract": lease_contract,
		"docstatus": 1,
	})
