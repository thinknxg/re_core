"""Shared helpers for Property Unit Charge rows (used by Property, Unit,
and Lease Contract auto-population)."""

from frappe.utils import flt

FREQUENCY_PERIODS_PER_YEAR = {
    "Monthly": 12,
    "Quarterly": 4,
    "Semi-Annual": 2,
    "Annual": 1,
}


def annualize(amount, frequency):
    """Convert a per-period charge amount into its annual equivalent."""
    periods = FREQUENCY_PERIODS_PER_YEAR.get(frequency, 1)
    return flt(flt(amount) * periods, 3)


def compute_annual_rent(charge_rows):
    """Sum the annualized amount of all 'Rent' type rows in a charges child table."""
    total = 0
    for row in (charge_rows or []):
        if row.charge_type == "Rent":
            total += annualize(row.amount, row.frequency)
    return flt(total, 3)


def build_lease_term_charges(property_name, unit_name, start_date, end_date):
    """Pull Property Unit Charge rows from both the Property and its Unit,
    convert each periodic amount into a total for the lease term, and return
    rows ready to append to a Lease Contract's 'charges' table.
    Property and Unit charges are independent - both are included, unrelated
    to each other (no fallback/priority between them).
    """
    import frappe
    from frappe.utils import month_diff

    duration_months = month_diff(end_date, start_date) or 1
    term_years = flt(duration_months) / 12

    rows = []
    sources = []
    if property_name:
        sources.extend(frappe.get_all(
            "Property Unit Charge",
            filters={"parent": property_name, "parenttype": "Property"},
            fields=["charge_type", "description", "amount", "frequency", "item_tax_template"],
        ))
    if unit_name:
        sources.extend(frappe.get_all(
            "Property Unit Charge",
            filters={"parent": unit_name, "parenttype": "Unit"},
            fields=["charge_type", "description", "amount", "frequency", "item_tax_template"],
        ))

    for row in sources:
        term_total = annualize(row.amount, row.frequency) * term_years
        rows.append({
            "charge_type": row.charge_type,
            "description": row.description,
            "amount": flt(term_total, 3),
            "item_tax_template": row.item_tax_template,
        })
    return rows
