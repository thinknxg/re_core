import frappe


def run():
    # Set app on both first (raw DB write, bypasses save-pipeline entirely,
    # avoids re-triggering the title/label revert behavior)
    frappe.db.set_value("Workspace Sidebar", "Property Ops", "app", "re_core")
    frappe.db.set_value("Desktop Icon", "Property Ops", "app", "re_core")
    frappe.db.commit()

    frappe.rename_doc("Workspace Sidebar", "Property Ops", "RE Core", force=True)
    frappe.rename_doc("Desktop Icon", "Property Ops", "RE Core", force=True)

    icon = frappe.get_doc("Desktop Icon", "RE Core")
    icon.link_to = "RE Core"
    icon.save()

    frappe.db.commit()

    print("Sidebar title:", frappe.db.get_value("Workspace Sidebar", "RE Core", "title"))
    print("Icon label:", frappe.db.get_value("Desktop Icon", "RE Core", "label"))
    print("Icon link_to:", frappe.db.get_value("Desktop Icon", "RE Core", "link_to"))
