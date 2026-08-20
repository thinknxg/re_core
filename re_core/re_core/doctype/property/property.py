import frappe
from frappe.model.document import Document
from re_core.re_core.charge_utils import compute_annual_rent, get_primary_rent_frequency
class Property(Document):
    def validate(self):
        self.total_units = frappe.db.count("Unit", {"property": self.name})
        self.annual_rent = compute_annual_rent(self.charges)
        self.rent_frequency = get_primary_rent_frequency(self.charges)
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
