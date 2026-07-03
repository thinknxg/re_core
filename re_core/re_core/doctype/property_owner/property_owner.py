import frappe
from frappe.model.document import Document


class PropertyOwner(Document):
    def validate(self):
        if not self.supplier and self.owner_name:
            self.supplier = self._get_or_make_supplier()

    def _get_or_make_supplier(self):
        existing = frappe.db.exists("Supplier", {"supplier_name": self.owner_name})
        if existing:
            return existing
        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = self.owner_name
        supplier.supplier_group = (
            frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
        )
        supplier.supplier_type = "Individual" if self.owner_type == "Individual" else "Company"
        supplier.insert(ignore_permissions=True)
        return supplier.name
