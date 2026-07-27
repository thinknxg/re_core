import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def get_csrf_token():
    """Plain-GET, CSRF-exempt endpoint so a static www page (no Desk boot,
    so no frappe.csrf_token available client-side) can fetch a valid token
    once on load and attach it to subsequent write calls. Guests get an
    empty token, which is fine since CSRF isn't enforced for guest sessions.
    """
    if frappe.session.user == "Guest":
        return ""
    try:
        return frappe.sessions.get_csrf_token()
    except AttributeError:
        # fallback for Frappe versions where this isn't exposed as a helper
        token = frappe.local.session.data.get("csrf_token")
        if not token:
            token = frappe.generate_hash()
            frappe.local.session.data.csrf_token = token
            frappe.local.session_obj.update(force=True)
        return token


def _get_customer_for_current_user():
    """Resolve the logged-in portal user to their linked Customer record."""
    user = frappe.session.user
    customer = frappe.db.get_value("Contact", {"user": user}, "customer")
    if not customer:
        customer = frappe.db.get_value("Customer", {"portal_user": user}, "name")
    if not customer:
        frappe.throw(_("No customer profile linked to this account."))
    return customer


def _unit_row_to_dict(row):
    return {
        "name": row.unit_name,
        "unit_no": row.unit_no,
        "unit_title": row.unit_title,
        "floor": row.floor,
        "unit_type": row.unit_type,
        "usage": row.usage,
        "status": row.status,
        "furnishing": row.furnishing,
        "parking_slots": row.parking_slots,
        "area_sqm": row.area_sqm,
        "bedrooms": row.bedrooms,
        "bathrooms": row.bathrooms,
        "annual_rent": row.annual_rent,
        "property": row.property,
        "property_name": row.property_name,
        "city": row.city,
        "area": row.area,
        "cover_image": row.cover_image,
        "latitude": row.latitude,
        "longitude": row.longitude,
    }


@frappe.whitelist(allow_guest=True)
def get_live_properties(location=None, unit_type=None, min_rent=None, max_rent=None,
                         bedrooms=None, start=0, page_length=12):
    """Returns vacant units published to the portal, joined to their parent
    Property for building-level context (city, area, cover image).
    A unit only appears if BOTH the unit itself (published_to_portal + status=Vacant)
    AND its parent Property (is_live) allow it.
    """
    conditions = ["u.published_to_portal = 1", "u.status = 'Vacant'", "p.is_live = 1"]
    values = {}

    if location:
        conditions.append(
            "(p.city = %(location)s OR p.area = %(location)s "
            "OR CONCAT(p.area, ', ', p.city) = %(location)s)"
        )
        values["location"] = location
    if unit_type:
        conditions.append("u.unit_type = %(unit_type)s")
        values["unit_type"] = unit_type
    if min_rent:
        conditions.append("u.annual_rent >= %(min_rent)s")
        values["min_rent"] = min_rent
    if max_rent:
        conditions.append("u.annual_rent <= %(max_rent)s")
        values["max_rent"] = max_rent
    if bedrooms:
        conditions.append("u.bedrooms >= %(bedrooms)s")
        values["bedrooms"] = bedrooms

    values["start"] = int(start or 0)
    values["page_length"] = int(page_length or 12)

    rows = frappe.db.sql(f"""
        SELECT
            u.name as unit_name, u.unit_no, u.unit_title, u.floor, u.unit_type,
            u.usage, u.status, u.furnishing, u.parking_slots, u.area_sqm,
            u.bedrooms, u.bathrooms, u.annual_rent,
            p.name as property, p.property_name, p.city, p.area,
            COALESCE(p.cover_image, (
                SELECT pp.image FROM `tabProperty Photo` pp
                WHERE pp.parent = p.name
                ORDER BY pp.is_cover DESC, pp.idx ASC
                LIMIT 1
            )) as cover_image,
            p.latitude, p.longitude
        FROM `tabUnit` u
        INNER JOIN `tabProperty` p ON u.property = p.name
        WHERE {" AND ".join(conditions)}
        ORDER BY u.modified DESC
        LIMIT %(page_length)s OFFSET %(start)s
    """, values, as_dict=True)

    return [_unit_row_to_dict(r) for r in rows]


@frappe.whitelist(allow_guest=True)
def get_property_detail(unit):
    """Full detail for a single unit's dossier view, including amenities
    (pulled from the parent Property's Table MultiSelect) and photos.
    """
    row = frappe.db.sql("""
        SELECT
            u.name as unit_name, u.unit_no, u.unit_title, u.floor, u.unit_type,
            u.usage, u.status, u.furnishing, u.parking_slots, u.area_sqm,
            u.bedrooms, u.bathrooms, u.annual_rent,
            p.name as property, p.property_name, p.city, p.area, p.address_line,
            p.cover_image, p.latitude, p.longitude
        FROM `tabUnit` u
        INNER JOIN `tabProperty` p ON u.property = p.name
        WHERE u.name = %(unit)s
    """, {"unit": unit}, as_dict=True)

    if not row:
        frappe.throw(_("Unit not found or not published."))

    data = _unit_row_to_dict(row[0])
    data["address_line"] = row[0].address_line

    # Amenities live on the parent Property as a Table MultiSelect
    amenities = frappe.get_all(
        "Property Amenity",
        filters={"parent": data["property"], "parenttype": "Property"},
        pluck="amenity",
    )
    data["amenities"] = amenities

    # Photos child table on Property
    photos = frappe.get_all(
        "Property Photo",
        filters={"parent": data["property"], "parenttype": "Property"},
        fields=["image", "caption", "is_cover"],
        order_by="is_cover desc",
    )
    data["photos"] = [p.image for p in photos]

    return data


@frappe.whitelist()
def toggle_wishlist(unit):
    customer = _get_customer_for_current_user()
    existing = frappe.db.exists("Property Wishlist", {"customer": customer, "unit": unit})
    if existing:
        frappe.delete_doc("Property Wishlist", existing, ignore_permissions=True)
        return {"saved": False}
    doc = frappe.get_doc({
        "doctype": "Property Wishlist",
        "customer": customer,
        "unit": unit,
    })
    doc.insert(ignore_permissions=True)
    return {"saved": True}


@frappe.whitelist(allow_guest=True)
def submit_enquiry(unit, name=None, phone=None, message=None):
    try:
        customer = _get_customer_for_current_user()
    except Exception:
        customer = None

    doc = frappe.get_doc({
        "doctype": "Property Enquiry",
        "unit": unit,
        "customer": customer,
        "enquiry_type": "General Enquiry",
        "message": message,
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def book_site_visit(unit, visit_date, visit_time_slot):
    customer = _get_customer_for_current_user()
    doc = frappe.get_doc({
        "doctype": "Site Visit Booking",
        "unit": unit,
        "customer": customer,
        "visit_date": visit_date,
        "visit_time_slot": visit_time_slot,
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist(allow_guest=True)
def calculate_rent_plan(annual_rent, cheques=4):
    """Splits the annual rent into an even cheque schedule — the standard
    rental payment-plan breakdown, replacing a sale-financing EMI calc.
    """
    annual_rent = float(annual_rent)
    cheques = int(cheques)
    per_cheque = round(annual_rent / cheques, 2)
    return {
        "annual_rent": annual_rent,
        "cheques": cheques,
        "per_cheque": per_cheque,
        "monthly_equivalent": round(annual_rent / 12, 2),
    }
