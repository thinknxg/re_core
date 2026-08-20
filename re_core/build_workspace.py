import frappe
import json


def run():
    doc = frappe.get_doc("Workspace", "RE Core")
    doc.set("links", [])

    cards = [
        ("Properties", [
            ("Property", "DocType"),
            ("Unit", "DocType"),
            ("Property Owner", "DocType"),
            ("Amenity", "DocType"),
            ("Property Document", "DocType"),
        ]),
        ("Leasing & Tenants", [
            ("Tenant", "DocType"),
            ("Lease Contract", "DocType"),
            ("Rent Schedule", "DocType"),
            ("Rent Installment", "DocType"),
            ("Security Deposit", "DocType"),
            ("Post Dated Cheque", "DocType"),
            ("Move In Out Inspection", "DocType"),
            ("Tenancy Bulk Payment", "DocType"),
            ("Rent Credit Balance", "DocType"),
        ]),
        ("Maintenance", [
            ("Maintenance Request", "DocType"),
            ("Maintenance Job", "DocType"),
        ]),
        ("Accounting", [
            ("Owner Statement", "DocType"),
            ("Expense Property", "DocType"),
            ("Utility Account", "DocType"),
        ]),
        ("Marketing & Enquiries", [
            ("Property Enquiry", "DocType"),
            ("Site Visit Booking", "DocType"),
            ("Property Wishlist", "DocType"),
            ("Saved Search", "DocType"),
        ]),
        ("CRM", [
            ("RE Lead", "DocType"),
            ("RE Deal", "DocType"),
            ("RE Agent", "DocType"),
            ("Site Visit", "DocType"),
            ("Reservation", "DocType"),
            ("Commission Entry", "DocType"),
            ("Lead Source RE", "DocType"),
            ("WhatsApp Message Log", "DocType"),
        ]),
        ("Portal / Listings", [
            ("Listing", "DocType"),
            ("Listing Inquiry", "DocType"),
            ("Listing Feed Settings", "DocType"),
        ]),
        ("Settings", [
            ("Property Settings", "DocType"),
            ("RE CRM Settings", "DocType"),
            ("RE Portal Settings", "DocType"),
            ("WhatsApp Settings", "DocType"),
        ]),
    ]

    content = [
        {"id": "re-core-header", "type": "header", "data": {"text": "<span class=\"h4\"><b>RE Core</b></span>", "col": 12}},
        {"id": "re-core-sub", "type": "paragraph", "data": {"text": "Property, leasing, CRM, and listings — all in one place.", "col": 12}},
    ]

    for card_label, links in cards:
        doc.append("links", {
            "type": "Card Break",
            "label": card_label,
            "link_count": len(links),
        })
        for link_label, link_type in links:
            doc.append("links", {
                "type": "Link",
                "label": link_label,
                "link_type": link_type,
                "link_to": link_label,
            })
        content.append({
            "id": "card-" + card_label.lower().replace(" ", "-").replace("/", ""),
            "type": "card",
            "data": {"card_name": card_label, "col": 4},
        })

    doc.content = json.dumps(content)
    doc.save()
    frappe.db.commit()
    print("Done. Cards:", len(cards), "Links:", len(doc.links))
