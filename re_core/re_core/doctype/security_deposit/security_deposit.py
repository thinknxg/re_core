import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class SecurityDeposit(Document):
    def on_submit(self):
        self.db_set("status", "Held")
        je = self._make_holding_entry()
        if je:
            self.db_set("journal_entry", je)

    def on_cancel(self):
        self.db_set("status", "Draft")

    def _accounts(self):
        settings = frappe.get_single("Property Settings")
        return settings.deposit_bank_account, settings.deposit_liability_account

    def _make_holding_entry(self):
        """Dr Bank / Cr Deposits Held. Skipped when accounts are not configured."""
        bank, liability = self._accounts()
        if not (bank and liability):
            return None
        je = frappe.new_doc("Journal Entry")
        je.company = self.company
        je.posting_date = self.received_date or nowdate()
        je.user_remark = _("Security deposit held for lease {0}").format(self.lease_contract)
        je.append("accounts", {"account": bank, "debit_in_account_currency": self.amount})
        je.append("accounts", {"account": liability, "credit_in_account_currency": self.amount})
        je.insert(ignore_permissions=True)
        je.submit()
        return je.name

    @frappe.whitelist()
    def refund(self, deduction_amount=0, deduction_reason=None):
        if self.docstatus != 1 or self.status != "Held":
            frappe.throw(_("Only Held deposits can be refunded."))
        deduction = flt(deduction_amount)
        if deduction > flt(self.amount):
            frappe.throw(_("Deduction cannot exceed the held amount."))
        refund_amount = flt(self.amount) - deduction
        self.db_set("deduction_amount", deduction)
        if deduction_reason:
            self.db_set("deduction_reason", deduction_reason)
        self.db_set("refunded_amount", refund_amount)
        if deduction and refund_amount:
            self.db_set("status", "Partially Refunded")
        elif refund_amount:
            self.db_set("status", "Refunded")
        else:
            self.db_set("status", "Forfeited")
        je = self._make_refund_entry(refund_amount)
        if je:
            self.db_set("refund_payment_entry", je)
        return self.status

    def _make_refund_entry(self, refund_amount):
        bank, liability = self._accounts()
        if not (bank and liability and refund_amount):
            return None
        je = frappe.new_doc("Journal Entry")
        je.company = self.company
        je.posting_date = nowdate()
        je.user_remark = _("Security deposit refund for lease {0}").format(self.lease_contract)
        je.append("accounts", {"account": liability, "debit_in_account_currency": refund_amount})
        je.append("accounts", {"account": bank, "credit_in_account_currency": refund_amount})
        je.insert(ignore_permissions=True)
        je.submit()
        return je.name
