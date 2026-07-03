import frappe
from frappe import _
from frappe.model.document import Document


class Unit(Document):
    def validate(self):
        prop = frappe.db.get_value("Property", self.property, "property_name") or self.property
        self.unit_title = f"{prop} / {self.unit_no}"

    def on_update(self):
        frappe.db.set_value("Property", self.property, "total_units",
                            frappe.db.count("Unit", {"property": self.property}) or 0,
                            update_modified=False)

    def on_trash(self):
        if self.status == "Occupied":
            frappe.throw(_("Cannot delete an occupied unit. Terminate the lease first."))
