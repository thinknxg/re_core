import frappe


def run():
    missing = ["Property", "Unit", "Amenity", "Tenant", "Maintenance Request", "Maintenance Job",
               "Owner Statement", "Utility Account", "Saved Search", "Tenant Portal Session",
               "Tenancy Bulk Payment", "Move In Out Inspection", "RE Agent", "Lead Source RE",
               "Listing Inquiry"]
    showing = ["Property Owner", "Property Document", "Lease Contract", "Rent Schedule",
               "Security Deposit", "Post Dated Cheque", "Rent Credit Balance", "Expense Property",
               "Property Enquiry", "Site Visit Booking", "Property Wishlist", "RE Lead", "RE Deal",
               "Site Visit", "Reservation", "Commission Entry", "WhatsApp Message Log", "Listing",
               "Listing Feed Settings"]

    print("--- MISSING doctypes' restrict_to_domain ---")
    for dt in missing:
        val = frappe.db.get_value("DocType", dt, "restrict_to_domain")
        print(f"  {dt}: {val}")

    print("\n--- SHOWING doctypes' restrict_to_domain ---")
    for dt in showing:
        val = frappe.db.get_value("DocType", dt, "restrict_to_domain")
        print(f"  {dt}: {val}")

    print("\n--- Active Domains on this site ---")
    print(frappe.get_active_domains())
