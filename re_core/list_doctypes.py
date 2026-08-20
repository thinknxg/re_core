import frappe


def run():
    for module in ["RE Core", "RE CRM", "RE Portal"]:
        rows = frappe.get_all("DocType", filters={"module": module, "istable": 0}, fields=["name"], order_by="name")
        print(f"\n=== {module} ({len(rows)}) ===")
        for r in rows:
            print(" -", r.name)
