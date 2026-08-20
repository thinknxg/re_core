import frappe


def run():
    missing = ["Property", "Unit", "Amenity", "Tenant", "Maintenance Request", "Maintenance Job",
               "Owner Statement", "Utility Account", "Saved Search", "Tenant Portal Session",
               "Tenancy Bulk Payment", "Move In Out Inspection", "RE Agent", "Lead Source RE",
               "Listing Inquiry"]
    showing = ["Property Owner", "Property Document", "Lease Contract", "Rent Schedule",
               "Security Deposit", "Post Dated Cheque", "Rent Credit Balance", "Expense Property",
               "Property Enquiry", "Site Visit Booking", "RE Lead", "RE Deal",
               "Site Visit", "Reservation", "Commission Entry", "WhatsApp Message Log", "Listing",
               "Listing Feed Settings"]

    print("--- MISSING doctypes: permission rows ---")
    for dt in missing:
        rows = frappe.get_all("DocPerm", filters={"parent": dt}, fields=["role", "read"])
        print(f"  {dt}: {rows}")

    print("\n--- SHOWING doctypes: permission rows ---")
    for dt in showing:
        rows = frappe.get_all("DocPerm", filters={"parent": dt}, fields=["role", "read"])
        print(f"  {dt}: {rows}")
