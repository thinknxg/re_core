import frappe
from frappe import _
from frappe.utils import flt


def create_owner_remittance(sales_invoice, method=None):
    """Hook: runs on Sales Invoice submit (the tenant's rent invoice).

    Real chain confirmed against re_core's actual schema:
      Sales Invoice
        <- Rent Installment.sales_invoice (find the installment referencing this invoice)
        -> Rent Installment.parent = Rent Schedule
        -> Rent Schedule.lease_contract = Lease Contract
        -> Lease Contract.unit / .property / .owner_ref (all direct fields)

    Fee precedence: Unit's management_fee_type/value overrides Property's,
    if the Unit has its own value set. Property Owner's management_fee_percent
    is NOT used here - confirmed out of scope for this calc.

    onetime_commission (our new field) is intentionally separate from
    Lease Contract's existing broker_commission - different concepts, both kept.

    Logic:
      1. Only proceed if Unit (or Property, as fallback) is Landlord-owned.
      2. Unit's fee override wins over Property's if Unit has a value set.
      3. Compute management fee (percentage of rent, or fixed amount).
      4. Deduct onetime_commission only on the first Purchase Invoice for
         this Lease Contract - checked via existing Purchase Invoices
         referencing the same lease_contract.
      5. Create Purchase Invoice against Property Owner's linked Supplier
         for net amount (rent - management_fee - onetime_commission_if_first).
    """
    installment = frappe.db.get_value(
        "Rent Installment",
        {"sales_invoice": sales_invoice.name},
        ["name", "parent"],
        as_dict=True,
    )
    if not installment:
        # This Sales Invoice isn't a rent invoice generated via Rent Schedule -
        # nothing to remit (e.g. a one-off charge, deposit invoice, etc.)
        return

    rent_schedule = frappe.get_doc("Rent Schedule", installment.parent)
    if not rent_schedule.lease_contract:
        return

    lease_contract = frappe.get_doc("Lease Contract", rent_schedule.lease_contract)

    unit = frappe.get_doc("Unit", lease_contract.unit) if lease_contract.unit else None
    property_doc = frappe.get_doc("Property", lease_contract.property) if lease_contract.property else None

    ownership_type = (unit.ownership_type if unit else None) or (
        property_doc.ownership_type if property_doc else None
    )
    if ownership_type != "Landlord":
        return  # Company-owned - no remittance needed

    owner_ref = lease_contract.owner_ref or (unit.owner_ref if unit else None) or (
        property_doc.owner_ref if property_doc else None
    )
    if not owner_ref:
        frappe.log_error(
            title="Owner Remittance Skipped - No Owner",
            message=f"Lease Contract {lease_contract.name} is Landlord-owned but has no Owner set. Sales Invoice: {sales_invoice.name}",
        )
        return

    owner_doc = frappe.get_doc("Property Owner", owner_ref)
    if not owner_doc.supplier:
        frappe.log_error(
            title="Owner Remittance Skipped - No Supplier",
            message=f"Property Owner {owner_ref} has no linked Supplier record. Sales Invoice: {sales_invoice.name}",
        )
        return

    # Unit override wins over Property, per confirmed precedence
    fee_type = (unit.management_fee_type if unit and unit.management_fee_type else None) \
        or (property_doc.management_fee_type if property_doc else "Percentage")
    fee_value = flt(
        (unit.management_fee_value if unit and unit.management_fee_value else None)
        or (property_doc.management_fee_value if property_doc else 0)
    )
    onetime_commission = flt(
        (unit.onetime_commission if unit and unit.onetime_commission else None)
        or (property_doc.onetime_commission if property_doc else 0)
    )

    rent_amount = flt(sales_invoice.grand_total)

    if fee_type == "Percentage":
        management_fee_amount = rent_amount * fee_value / 100
    else:
        management_fee_amount = fee_value

    existing_remittance_count = frappe.db.count(
        "Purchase Invoice",
        filters={"custom_lease_contract": lease_contract.name, "docstatus": 1},
    )
    is_first_invoice = existing_remittance_count == 0
    commission_to_deduct = onetime_commission if is_first_invoice else 0

    net_payable = rent_amount - management_fee_amount - commission_to_deduct

    if net_payable <= 0:
        frappe.log_error(
            title="Owner Remittance - Non-positive net amount",
            message=(
                f"Computed net payable to owner is {net_payable} for Sales Invoice "
                f"{sales_invoice.name} (Lease Contract {lease_contract.name}). "
                f"Skipping Purchase Invoice creation - check fee values."
            ),
        )
        return

    pi = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": owner_doc.supplier,
        "custom_source_sales_invoice": sales_invoice.name,
        "custom_lease_contract": lease_contract.name,
        "items": [{
            "item_code": _get_or_create_remittance_item(),
            "qty": 1,
            "rate": net_payable,
            "description": (
                f"Owner remittance for {sales_invoice.name} - rent {rent_amount}, "
                f"less management fee {management_fee_amount}"
                + (f", less onetime commission {commission_to_deduct}" if commission_to_deduct else "")
            ),
        }],
    })
    pi.insert(ignore_permissions=True)

    frappe.msgprint(
        _("Owner remittance Purchase Invoice {0} created for {1}").format(pi.name, owner_doc.supplier),
        alert=True,
    )


def _get_or_create_remittance_item():
    """Ensures a service Item exists to represent 'Owner Rent Remittance' line items
    on the generated Purchase Invoices. Adjust item group/defaults as needed.
    """
    item_code = "Owner Rent Remittance"
    if not frappe.db.exists("Item", item_code):
        frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_code,
            "item_group": "Services",
            "is_stock_item": 0,
        }).insert(ignore_permissions=True)
    return item_code
