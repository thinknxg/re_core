import frappe
from frappe import _
from frappe.utils import flt


def create_deposit_journal_entry(doc, method=None):
    """Hook: Security Deposit on_submit. Books the receipt as a liability."""
    if not doc.deposit_account:
        frappe.throw(_("Deposit Account must be set before submitting."))

    liability_account = _get_liability_account(doc.company)

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = doc.company
    je.posting_date = doc.received_date or frappe.utils.today()
    je.user_remark = _("Security Deposit received - {0}").format(doc.name)
    je.append("accounts", {"account": doc.deposit_account, "debit_in_account_currency": doc.amount})
    je.append("accounts", {"account": liability_account, "credit_in_account_currency": doc.amount,
                            "party_type": "Customer",
                            "party": frappe.db.get_value("Tenant", doc.tenant, "customer")})
    je.insert(ignore_permissions=True)
    je.submit()

    frappe.db.set_value("Security Deposit", doc.name, "journal_entry", je.name)
    frappe.msgprint(_("Journal Entry {0} created for deposit").format(je.name), alert=True)


def process_refund_or_forfeit(doc, deduction_amount, refund_amount):
    """Called from update_security_deposit after status/amounts are saved.
    Books forfeiture (if any) to income, and refund (if any) as a Payment Entry.
    """
    liability_account = _get_liability_account(doc.company)
    customer = frappe.db.get_value("Tenant", doc.tenant, "customer")
    if not customer:
        frappe.throw(_("Tenant {0} has no linked Customer.").format(doc.tenant))

    if flt(deduction_amount) > 0:
        income_account = _get_forfeiture_income_account(doc.company)
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.company = doc.company
        je.posting_date = frappe.utils.today()
        je.user_remark = _("Security Deposit deduction - {0}").format(doc.name)
        je.append("accounts", {"account": liability_account, "debit_in_account_currency": deduction_amount,
                                "party_type": "Customer", "party": customer})
        je.append("accounts", {"account": income_account, "credit_in_account_currency": deduction_amount})
        je.insert(ignore_permissions=True)
        je.submit()

    if flt(refund_amount) > 0:
        if not doc.deposit_account:
            frappe.throw(_("Deposit Account must be set to process a refund."))

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Pay"
        pe.party_type = "Customer"
        pe.party = customer
        pe.company = doc.company
        pe.paid_from = liability_account
        pe.paid_to = doc.deposit_account
        pe.paid_amount = refund_amount
        pe.received_amount = refund_amount
        if doc.mode_of_payment:
            pe.mode_of_payment = doc.mode_of_payment
        pe.reference_no = doc.name
        pe.reference_date = frappe.utils.today()
        pe.insert(ignore_permissions=True)
        pe.submit()

        frappe.db.set_value("Security Deposit", doc.name, "refund_payment_entry", pe.name)
        frappe.msgprint(_("Payment Entry {0} created for refund").format(pe.name), alert=True)


def _get_liability_account(company):
    abbr = frappe.db.get_value("Company", company, "abbr")
    account = f"Tenant Security Deposits Payable - {abbr}"
    if not frappe.db.exists("Account", account):
        frappe.throw(_("Liability account {0} not found - run the account setup script first.").format(account))
    return account


def _get_forfeiture_income_account(company):
    abbr = frappe.db.get_value("Company", company, "abbr")
    account = f"Forfeited Security Deposits - {abbr}"
    if not frappe.db.exists("Account", account):
        frappe.throw(_("Income account {0} not found - run the account setup script first.").format(account))
    return account
