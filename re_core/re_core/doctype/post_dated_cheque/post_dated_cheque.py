import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

TRANSITIONS = {
    "Received": {"Deposited", "Returned", "Replaced"},
    "Deposited": {"Cleared", "Bounced"},
    "Bounced": {"Replaced", "Deposited"},
}


class PostDatedCheque(Document):
    def _move(self, new_status):
        if new_status not in TRANSITIONS.get(self.status, set()):
            frappe.throw(_("Cannot move PDC from {0} to {1}.").format(self.status, new_status))
        self.db_set("status", new_status)

    @frappe.whitelist()
    def mark_deposited(self):
        self._check_submitted()
        self._move("Deposited")
        self.db_set("deposit_date", nowdate())

    @frappe.whitelist()
    def mark_cleared(self):
        self._check_submitted()
        self._move("Cleared")
        self.db_set("clearance_date", nowdate())
        pe = self._make_payment_entry()
        if pe:
            self.db_set("payment_entry", pe)
        self._update_installment("Paid")

    @frappe.whitelist()
    def mark_bounced(self, reason=None):
        self._check_submitted()
        self._move("Bounced")
        if reason:
            self.db_set("bounce_reason", reason)
        self._update_installment("Bounced")
        self._notify_bounce()

    def _check_submitted(self):
        if self.docstatus != 1:
            frappe.throw(_("Submit the PDC before updating its lifecycle."))

    def _installment(self):
        return frappe.db.get_value(
            "Rent Installment", {"pdc": self.name},
            ["name", "sales_invoice", "parent"], as_dict=True)

    def _update_installment(self, status):
        inst = self._installment()
        if inst:
            frappe.db.set_value("Rent Installment", inst.name, "status", status)

    def _make_payment_entry(self):
        """Create a Payment Entry against the installment's Sales Invoice, if invoiced."""
        inst = self._installment()
        if not (inst and inst.sales_invoice):
            return None
        si = frappe.get_doc("Sales Invoice", inst.sales_invoice)
        if si.docstatus != 1 or not si.outstanding_amount:
            return None
        from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
        pe = get_payment_entry("Sales Invoice", si.name,
                               party_amount=min(self.amount, si.outstanding_amount))
        pe.reference_no = self.cheque_no
        pe.reference_date = self.clearance_date or nowdate()
        if self.deposit_account:
            pe.paid_to = self.deposit_account
        pe.insert(ignore_permissions=True)
        pe.submit()
        return pe.name

    def _notify_bounce(self):
        for user in frappe.get_all("Has Role",
                                   filters={"role": "Accounts User", "parenttype": "User"},
                                   pluck="parent"):
            if frappe.db.get_value("User", user, "enabled"):
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "for_user": user,
                    "type": "Alert",
                    "document_type": self.doctype,
                    "document_name": self.name,
                    "subject": _("PDC {0} ({1}) bounced").format(self.cheque_no, self.tenant),
                }).insert(ignore_permissions=True)
