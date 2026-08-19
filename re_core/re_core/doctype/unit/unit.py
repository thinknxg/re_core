import frappe
from frappe import _
from frappe.model.document import Document
from re_core.re_core.charge_utils import compute_annual_rent
class Unit(Document):
    def validate(self):
        prop_fields = frappe.db.get_value(
            "Property",
            self.property,
            [
                "property_name",
                "ownership_type",
                "owner_ref",
                "management_fee_type",
                "management_fee_value",
                "onetime_commission",
            ],
            as_dict=True,
        ) or {}
        prop_name = prop_fields.get("property_name") or self.property
        self.unit_title = f"{prop_name} / {self.unit_no}"
        # ownership_type / owner_ref are read-only mirrors of Property — always sync
        self.ownership_type = prop_fields.get("ownership_type")
        self.owner_ref = prop_fields.get("owner_ref")
        # management fee fields are editable per-unit overrides —
        # only default them from Property on first creation, never overwrite after
        if self.is_new():
            if not self.management_fee_type:
                self.management_fee_type = prop_fields.get("management_fee_type")
            if not self.management_fee_value:
                self.management_fee_value = prop_fields.get("management_fee_value")
            if not self.onetime_commission:
                self.onetime_commission = prop_fields.get("onetime_commission")
        self.annual_rent = compute_annual_rent(self.charges)
    def on_update(self):
        frappe.db.set_value("Property", self.property, "total_units",
                            frappe.db.count("Unit", {"property": self.property}) or 0,
                            update_modified=False)
    def on_trash(self):
        if self.status == "Occupied":
            frappe.throw(_("Cannot delete an occupied unit. Terminate the lease first."))
