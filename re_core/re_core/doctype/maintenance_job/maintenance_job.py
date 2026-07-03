import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class MaintenanceJob(Document):
    def validate(self):
        self.total_cost = flt(self.material_cost) + flt(self.labor_cost)
        if not self.company:
            unit = frappe.db.get_value("Maintenance Request", self.maintenance_request, "unit")
            prop = frappe.db.get_value("Unit", unit, "property")
            self.company = frappe.db.get_value("Property", prop, "company")

    def on_submit(self):
        if not self.completion_date:
            self.db_set("completion_date", nowdate())
        frappe.db.set_value("Maintenance Request", self.maintenance_request,
                            "status", "Completed")
        if self.billable_to == "Tenant" and flt(self.total_cost) > 0:
            si = self._bill_tenant()
            if si:
                self.db_set("sales_invoice", si)

    def _bill_tenant(self):
        request = frappe.get_doc("Maintenance Request", self.maintenance_request)
        if not request.tenant:
            return None
        customer = frappe.db.get_value("Tenant", request.tenant, "customer")
        rent_item = frappe.db.get_single_value("Property Settings", "rent_item")
        if not (customer and rent_item):
            return None
        si = frappe.new_doc("Sales Invoice")
        si.customer = customer
        si.company = self.company
        si.append("items", {
            "item_code": rent_item,
            "item_name": _("Maintenance recharge: {0}").format(self.name),
            "description": self.work_notes or self.name,
            "qty": 1,
            "rate": self.total_cost,
        })
        si.insert(ignore_permissions=True)
        return si.name

    def on_cancel(self):
        frappe.db.set_value("Maintenance Request", self.maintenance_request,
                            "status", "In Progress")
