import frappe
from frappe import _
from frappe.model.mapper import get_payment_entry


def create_or_sync_payment_entry(pdc_doc, method=None):
    """Hook: runs on Post Dated Cheque submit.

    If the PDC already has a linked Payment Entry (e.g. bulk flow, where
    record_partial_payment() already created and submitted one before this
    PDC record was even created), just sync the bank/mode onto it.

    Otherwise, create a new draft Payment Entry - linked to the reserved
    installment's Sales Invoice if one exists, or a standalone receipt
    against the tenant's Customer if not.
    """
    if not pdc_doc.deposit_account:
        frappe.throw(_("Deposit Account must be set before submitting this cheque."))

    if pdc_doc.payment_entry:
        _sync_existing_payment_entry(pdc_doc)
    else:
        _create_payment_entry(pdc_doc)


def _sync_existing_payment_entry(pdc_doc):
    pe = frappe.get_doc("Payment Entry", pdc_doc.payment_entry)
    if pe.docstatus == 1:
        frappe.throw(
            _("Linked Payment Entry {0} is already submitted - cannot change bank now.").format(pe.name)
        )

    pe.paid_to = pdc_doc.deposit_account
    if pdc_doc.mode_of_payment:
        pe.mode_of_payment = pdc_doc.mode_of_payment
    pe.save(ignore_permissions=True)

    frappe.msgprint(
        _("Payment Entry {0} updated to use deposit account {1}").format(pe.name, pdc_doc.deposit_account),
        alert=True,
    )


def _create_payment_entry(pdc_doc):
    row = frappe.db.get_value(
        "Rent Installment",
        {"pdc": pdc_doc.name, "parenttype": "Rent Schedule"},
        ["name", "parent", "sales_invoice"],
        as_dict=True,
    )

    if row and row.sales_invoice:
        pe = get_payment_entry("Sales Invoice", row.sales_invoice, party_amount=pdc_doc.amount)
    else:
        customer = frappe.db.get_value("Tenant", pdc_doc.tenant, "customer")
        if not customer:
            frappe.throw(_("Tenant {0} has no linked Customer.").format(pdc_doc.tenant))

        receivable_account = frappe.get_cached_value(
            "Company", pdc_doc.company, "default_receivable_account"
        )
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.party_type = "Customer"
        pe.party = customer
        pe.company = pdc_doc.company
        pe.paid_from = receivable_account
        pe.paid_amount = pdc_doc.amount
        pe.received_amount = pdc_doc.amount

    pe.paid_to = pdc_doc.deposit_account
    if pdc_doc.mode_of_payment:
        pe.mode_of_payment = pdc_doc.mode_of_payment
    pe.reference_no = pdc_doc.cheque_no
    pe.reference_date = pdc_doc.cheque_date
    pe.posting_date = pdc_doc.cheque_date
    pe.insert(ignore_permissions=True)

    frappe.db.set_value("Post Dated Cheque", pdc_doc.name, "payment_entry", pe.name)

    frappe.msgprint(
        _("Payment Entry {0} created for cheque {1}").format(pe.name, pdc_doc.cheque_no),
        alert=True,
    )
