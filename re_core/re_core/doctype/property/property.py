import frappe
from frappe.model.document import Document


class Property(Document):
    def validate(self):
        self.total_units = frappe.db.count("Unit", {"property": self.name})
