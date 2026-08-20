import frappe


def run():
    doc = frappe.get_doc("Workspace", "RE Core")
    print("Total link rows saved:", len(doc.links))
    for l in doc.links:
        print(f"  [{l.type}] {l.label}  (link_to={l.link_to})")
