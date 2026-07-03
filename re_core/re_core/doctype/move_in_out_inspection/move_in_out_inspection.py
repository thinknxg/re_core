import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MoveInOutInspection(Document):
    def on_submit(self):
        if self.inspection_type == "Move Out" and flt(self.estimated_damage_cost) > 0:
            deposit = frappe.db.get_value("Lease Contract", self.lease_contract,
                                          "security_deposit")
            if deposit:
                frappe.db.set_value("Security Deposit", deposit, {
                    "deduction_amount": self.estimated_damage_cost,
                    "deduction_reason": _("Move-out inspection {0}: {1}").format(
                        self.name, self.summary or ""),
                })
                frappe.msgprint(_("Deduction of {0} staged on Security Deposit {1}.")
                                .format(self.estimated_damage_cost, deposit))
