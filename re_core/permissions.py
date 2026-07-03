"""Row-level isolation for portal Tenant users (wired in hooks)."""

import frappe

TENANT_LINKED = {
    "Lease Contract": "tenant",
    "Rent Schedule": "tenant",
    "Post Dated Cheque": "tenant",
    "Security Deposit": "tenant",
    "Maintenance Request": "tenant",
    "Tenant": "name",
}


def _tenant_of(user):
    from re_core.re_core.doctype.tenant.tenant import get_tenant_for_user
    return get_tenant_for_user(user)


def _is_portal_tenant(user):
    roles = frappe.get_roles(user)
    return "Tenant" in roles and not ({"RE Manager", "Property Manager", "Leasing Officer",
                                       "Accounts User", "System Manager",
                                       "Maintenance Supervisor"} & set(roles))


def make_query_condition(doctype):
    field = TENANT_LINKED[doctype]

    def query_condition(user):
        user = user or frappe.session.user
        if not _is_portal_tenant(user):
            return None
        tenant = _tenant_of(user)
        if not tenant:
            return "1=0"
        return f"`tab{doctype}`.`{field}` = {frappe.db.escape(tenant)}"

    return query_condition


lease_contract_query = make_query_condition("Lease Contract")
rent_schedule_query = make_query_condition("Rent Schedule")
pdc_query = make_query_condition("Post Dated Cheque")
security_deposit_query = make_query_condition("Security Deposit")
maintenance_request_query = make_query_condition("Maintenance Request")
tenant_query = make_query_condition("Tenant")


def has_permission(doc, ptype, user):
    """Belt-and-braces per-document check for tenant users."""
    if not _is_portal_tenant(user):
        return True
    tenant = _tenant_of(user)
    field = TENANT_LINKED.get(doc.doctype)
    if not field:
        return False
    value = doc.name if field == "name" else doc.get(field)
    return bool(tenant) and value == tenant
