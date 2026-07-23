import frappe
from frappe import _


def sync_bank_to_payment_entry(pdc_doc, method=None):
    """Hook: runs on Post Dated Cheque submit.

    Confirmed against real schema: Post Dated Cheque's field is
    "payment_entry" (not "linked_payment_entry" as originally guessed).

    Payment Entry's bank-side field is "party_bank_account" (standard
    Frappe field) - adjust if you're using a custom field instead.
    Mode of Payment is resolved via Bank Account -> Account -> linked
    Mode of Payment. Adjust _resolve_mode_of_payment() if your setup
    maps Mode of Payment differently.

    This allows the bank to be changed right up to the moment of submission
    and have the accounting Payment Entry submit against the correct
    bank/mode, rather than whatever bank was set when the PDC was first created.
    """
    if not pdc_doc.bank_account:
        frappe.throw(_("Bank Account must be set before submitting this cheque."))

    linked_pe_name = pdc_doc.payment_entry
    if not linked_pe_name:
        # No Payment Entry exists yet for this PDC - nothing to sync.
        # If your flow creates the Payment Entry as part of this same submit
        # action rather than beforehand, call that creation function here
        # instead, passing pdc_doc.bank_account through to it.
        return

    pe = frappe.get_doc("Payment Entry", linked_pe_name)
    if pe.docstatus == 1:
        frappe.throw(
            _("Linked Payment Entry {0} is already submitted - cannot change bank now.").format(pe.name)
        )

    pe.party_bank_account = pdc_doc.bank_account
    mode_of_payment = _resolve_mode_of_payment(pdc_doc.bank_account)
    if mode_of_payment:
        pe.mode_of_payment = mode_of_payment

    pe.save(ignore_permissions=True)

    frappe.msgprint(
        _("Payment Entry {0} updated to use bank account {1}").format(pe.name, pdc_doc.bank_account),
        alert=True,
    )


def _resolve_mode_of_payment(bank_account_name):
    """Best-effort lookup of a Mode of Payment tied to the selected Bank Account.
    Adjust this if your Mode of Payment <-> Bank Account relationship is modeled
    differently (e.g. a direct custom field rather than via Mode of Payment Account).
    """
    account = frappe.db.get_value("Bank Account", bank_account_name, "account")
    if not account:
        return None

    mop_account = frappe.db.get_value(
        "Mode of Payment Account", {"default_account": account}, "parent"
    )
    return mop_account
