import frappe
from frappe.model.document import Document

class Property(Document):
    def validate(self):
        self.total_units = frappe.db.count("Unit", {"property": self.name})

    def on_update(self):
        if self.has_value_changed("ownership_type") or self.has_value_changed("owner_ref"):
            units = frappe.get_all("Unit", filters={"property": self.name}, pluck="name")
            for unit_name in units:
                frappe.db.set_value(
                    "Unit",
                    unit_name,
                    {
                        "ownership_type": self.ownership_type,
                        "owner_ref": self.owner_ref,
                    },
                    update_modified=False,
                )
            if units:
                frappe.db.commit()
