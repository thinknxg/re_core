import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RentSchedule(Document):
    def validate(self):
        self.total_amount = sum(flt(r.amount) for r in self.installments)
        if self.installments and all(r.status in ("Paid", "Cancelled") for r in self.installments):
            if self.status == "Active":
                self.status = "Completed"
