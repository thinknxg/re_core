import frappe


def run():
    frappe.set_user("Administrator")
    print("Administrator roles:", frappe.get_roles("Administrator"))

    for dt in ["Unit", "Property", "Maintenance Request", "Property Owner", "Lease Contract"]:
        print(f"{dt}: has_permission={frappe.has_permission(dt, 'read')}")
