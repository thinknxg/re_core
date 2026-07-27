# Copyright (c) 2026, Kreatao and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

EXPENSE_ACCOUNT_MAP = {
    "Maintenance": "Repairs and Maintenance",
    "Utilities": "Utilities",
    "Municipality Fee": "Rates and Taxes",
    "Insurance": "Insurance",
    "Staff": "Staff Welfare",
}


class ExpenseProperty(Document):
    def on_submit(self):
        je = self.create_journal_entry()
        self.db_set("paid_amount", 0)
        self.db_set("outstanding_amount", flt(self.amount))
        self.db_set("journal_entry", je.name)
        self.db_set("status", "Posted")

    def get_company(self):
        return self.company or frappe.db.get_value("Property", self.property, "company")

    def get_expense_account(self, company):
        account_name = EXPENSE_ACCOUNT_MAP.get(self.expense_type)
        account = None
        if account_name:
            account = frappe.db.get_value(
                "Account", {"account_name": account_name, "company": company}
            )
        if not account:
            account = frappe.db.get_value("Company", company, "default_expense_account")
        if not account:
            frappe.throw(
                _("No account found for expense type {0} and no Default Expense Account set on {1}")
                .format(self.expense_type, company)
            )
        return account

    def create_journal_entry(self):
        if not self.supplier:
            frappe.throw(_("Supplier is required to post this expense."))

        company = self.get_company()
        expense_account = self.get_expense_account(company)
        payable_account = frappe.db.get_value("Company", company, "default_payable_account")

        if not payable_account:
            frappe.throw(_("Please set a Default Payable Account for company {0}").format(company))

        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = self.expense_date or nowdate()
        je.company = company
        je.user_remark = _("Expense Property {0} - {1}").format(self.name, self.expense_type)

        je.append("accounts", {
            "account": expense_account,
            "debit_in_account_currency": flt(self.amount),
        })
        je.append("accounts", {
            "account": payable_account,
            "credit_in_account_currency": flt(self.amount),
            "party_type": "Supplier",
            "party": self.supplier,
            "is_advance": "Yes",
        })

        je.insert(ignore_permissions=True)
        je.submit()
        return je


@frappe.whitelist()
def record_partial_payment(expense_property, paid_amount, payment_date=None, remarks=None):
    doc = frappe.get_doc("Expense Property", expense_property)

    if doc.docstatus != 1:
        frappe.throw(_("Expense Property must be submitted before recording a payment."))
    if not doc.supplier:
        frappe.throw(_("Supplier is required to record a payment."))

    paid_amount = flt(paid_amount)
    outstanding = flt(doc.outstanding_amount)

    if paid_amount <= 0:
        frappe.throw(_("Paid amount must be greater than zero."))
    if paid_amount > outstanding:
        frappe.throw(_("Paid amount cannot exceed outstanding amount of {0}").format(outstanding))

    payment_date = payment_date or nowdate()
    company = doc.get_company()

    payable_account = frappe.db.get_value("Company", company, "default_payable_account")
    cash_account = frappe.db.get_value("Company", company, "default_cash_account")

    if not cash_account:
        frappe.throw(_("Please set a Default Cash Account for company {0}").format(company))

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = payment_date
    je.company = company
    je.user_remark = _("Payment against Expense Property {0}").format(doc.name)

    je.append("accounts", {
        "account": payable_account,
        "debit_in_account_currency": paid_amount,
        "party_type": "Supplier",
        "party": doc.supplier,
        "is_advance": "Yes",
    })
    je.append("accounts", {
        "account": cash_account,
        "credit_in_account_currency": paid_amount,
    })

    je.insert(ignore_permissions=True)
    je.submit()

    payment_row = frappe.get_doc({
        "doctype": "Partial Payment Table",
        "parent": doc.name,
        "parenttype": "Expense Property",
        "parentfield": "partial_payments",
        "journal_entry": je.name,
        "payment_date": payment_date,
        "paid_amount": paid_amount,
        "outstanding_amount": outstanding - paid_amount,
        "remarks": remarks,
    })
    payment_row.insert(ignore_permissions=True)

    new_paid = flt(doc.paid_amount) + paid_amount
    new_outstanding = outstanding - paid_amount
    new_status = "Paid" if new_outstanding <= 0 else "Partially Paid"
    doc.db_set("paid_amount", new_paid)
    doc.db_set("outstanding_amount", new_outstanding)
    doc.db_set("status", new_status)

    return je.name
