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


def get_primary_rent_frequency(charge_rows):
    """Return the Frequency of the first 'Rent' type row, for display purposes
    (e.g. showing '25,000/mo' on listings instead of always annualizing)."""
    for row in (charge_rows or []):
        if row.charge_type == "Rent":
            return row.frequency
    return None


def term_years_between(start_date, end_date):
    from frappe.utils import month_diff
    duration_months = month_diff(end_date, start_date) or 1
    return flt(duration_months) / 12


def per_period_to_term_total(amount, frequency, start_date, end_date):
    """Convert a per-period amount + frequency into a total for the given lease term."""
    return flt(annualize(amount, frequency) * term_years_between(start_date, end_date), 3)


def build_lease_term_charges(property_name, unit_name, start_date, end_date):
    """Pull Property Unit Charge rows from both the Property and its Unit,
    convert each periodic amount into a total for the lease term, and return
    rows ready to append to a Lease Contract's 'charges' table. Each row also
    carries its original per-period 'source_amount' and 'frequency' so the
    frontend can display/edit them the same way as on Property/Unit, rather
    than only showing the converted term total.
    Property and Unit charges are independent - both are included, unrelated
    to each other (no fallback/priority between them).
    """
    import frappe

    term_years = term_years_between(start_date, end_date)

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
        term_total = flt(annualize(row.amount, row.frequency) * term_years, 3)
        rows.append({
            "charge_type": row.charge_type,
            "description": row.description,
            "amount": term_total,
            "item_tax_template": row.item_tax_template,
            "source_amount": row.amount,
            "frequency": row.frequency,
        })
    return rows
