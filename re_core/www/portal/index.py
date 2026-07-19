import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/portal"
        raise frappe.Redirect

    fullname = frappe.utils.get_fullname(frappe.session.user)
    parts = fullname.split()
    initials = "".join(p[0].upper() for p in parts[:2]) if parts else "U"

    roles = frappe.get_roles(frappe.session.user)
    primary_role = "System Manager" if "System Manager" in roles else (roles[0] if roles else "User")

    context.csrf_token = frappe.sessions.get_csrf_token()
    context.user_fullname = fullname
    context.user_initials = initials
    context.user_role = primary_role
