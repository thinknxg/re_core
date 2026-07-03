import frappe
from frappe import _
from frappe.model.document import Document


class MaintenanceRequest(Document):
    def validate(self):
        # Portal-raised: bind to the session tenant and verify unit ownership
        from re_core.re_core.doctype.tenant.tenant import get_tenant_for_user
        tenant = get_tenant_for_user()
        if tenant:
            self.tenant = tenant
            active = frappe.db.get_value(
                "Lease Contract",
                {"tenant": tenant, "unit": self.unit, "status": ["in", ["Active", "Expiring"]],
                 "docstatus": 1}, "name")
            if not active:
                frappe.throw(_("You can only raise requests for a unit you currently lease."))

    @frappe.whitelist()
    def make_job(self):
        if self.maintenance_job:
            frappe.throw(_("A job already exists for this request."))
        job = frappe.new_doc("Maintenance Job")
        job.maintenance_request = self.name
        job.company = frappe.db.get_value("Property", self.property, "company")
        job.insert(ignore_permissions=True)
        self.db_set("maintenance_job", job.name)
        self.db_set("status", "In Progress")
        return job.name
