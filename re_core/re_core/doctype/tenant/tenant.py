import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url


class Tenant(Document):
    def validate(self):
        if not self.whatsapp_number:
            self.whatsapp_number = self.mobile
        if not self.customer:
            self.customer = self._get_or_make_customer()
        if self.enable_portal and not self.email:
            frappe.throw(_("An email address is required to enable the tenant portal."))

    def on_update(self):
        if self.enable_portal and not self.portal_user:
            self._provision_portal_user()

    def _get_or_make_customer(self):
        existing = frappe.db.exists("Customer", {"customer_name": self.tenant_name})
        if existing:
            return existing
        customer = frappe.new_doc("Customer")
        customer.customer_name = self.tenant_name
        customer.customer_type = "Individual" if self.tenant_type == "Individual" else "Company"
        group = frappe.db.exists("Customer Group", "Tenants")
        if not group:
            grp = frappe.new_doc("Customer Group")
            grp.customer_group_name = "Tenants"
            grp.parent_customer_group = frappe.db.get_value(
                "Customer Group", {"is_group": 1, "parent_customer_group": ""}, "name")
            grp.insert(ignore_permissions=True)
            group = grp.name
        customer.customer_group = group
        customer.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
        customer.mobile_no = self.mobile
        customer.insert(ignore_permissions=True)
        return customer.name

    def _provision_portal_user(self):
        if frappe.db.exists("User", self.email):
            user = frappe.get_doc("User", self.email)
        else:
            user = frappe.new_doc("User")
            user.email = self.email
            user.first_name = self.tenant_name
            user.user_type = "Website User"
            user.send_welcome_email = 1
            user.insert(ignore_permissions=True)
        user.add_roles("Tenant")
        self.db_set("portal_user", user.name)
        frappe.msgprint(_("Tenant portal user {0} provisioned. Login: {1}").format(
            user.name, get_url("/tenant-portal")))


def get_tenant_for_user(user=None):
    """Resolve the Tenant record for a session user (used by portal APIs and permission hooks)."""
    user = user or frappe.session.user
    if user in ("Guest", "Administrator"):
        return None
    return frappe.db.get_value("Tenant", {"portal_user": user, "disabled": 0}, "name")
