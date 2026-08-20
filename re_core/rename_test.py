import frappe


def run():
    sidebar = frappe.get_doc("Workspace Sidebar", "Property Ops")
    sidebar.title = "RE Core"
    sidebar.save()
    frappe.db.commit()

    # Re-fetch immediately, bypassing any doc cache, straight from DB
    frappe.clear_cache()
    val_immediately_after = frappe.db.get_value("Workspace Sidebar", "Property Ops", "title")
    print("Title immediately after save+commit:", val_immediately_after)

    icon = frappe.get_doc("Desktop Icon", "Property Ops")
    icon.label = "RE Core"
    icon.standard = 1
    icon.save()
    frappe.db.commit()

    frappe.clear_cache()
    val2 = frappe.db.get_value("Desktop Icon", "Property Ops", "label")
    print("Icon label immediately after save+commit:", val2)
