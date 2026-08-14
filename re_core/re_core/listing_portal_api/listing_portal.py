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
    """No direct Customer<->User link exists in this schema. Portal visitors
    resolve via Lead (see _get_identity_for_current_user); a Customer only
    exists later, once someone becomes an actual Tenant.
    """
    frappe.throw(_("No customer profile linked to this account."))


def _get_identity_for_current_user():
    """Resolve the logged-in portal user to either a Customer (if they've since
    become a real tenant) or their auto-created portal Lead. Returns a dict
    {"customer": name_or_None, "lead": name_or_None}. Throws if the user has
    neither - i.e. not actually logged in via the portal.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please log in to do that."))

    lead = frappe.db.get_value("User", user, "portal_lead")

    if not lead:
        frappe.throw(_("This account isn't set up as a portal visitor. Please log in with the account you used to sign up on the listings page."))
    return {"customer": None, "lead": lead}


@frappe.whitelist(allow_guest=True)
def portal_signup(email, first_name, phone=None, password=None):
    email = (email or "").strip().lower()
    if not email or not first_name:
        frappe.throw(_("Name and email are required."))
    if frappe.db.exists("User", email):
        frappe.throw(_("An account with this email already exists. Please log in instead."))

    lead = frappe.get_doc({
        "doctype": "Lead",
        "lead_name": first_name,
        "email_id": email,
        "mobile_no": phone,
        "source": "Website Listings Portal",
    })
    lead.insert(ignore_permissions=True)

    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "phone": phone,
        "send_welcome_email": 0,
        "user_type": "Website User",
        "portal_lead": lead.name,
    })
    user.insert(ignore_permissions=True)
    if password:
        user.new_password = password
        user.save(ignore_permissions=True)

    frappe.db.commit()

    try:
        frappe.sendmail(
            recipients=email,
            subject=_("Welcome to RE Core Listings"),
            message=_(
                "Hi {0},<br><br>"
                "Your account is ready. You can now save listings to your wishlist, "
                "book site visits, and submit lease requests directly from the portal.<br><br>"
                "— RE Core"
            ).format(first_name),
            now=True,
        )
    except Exception:
        frappe.log_error(title="Portal signup email failed", message=frappe.get_traceback())

    frappe.local.login_manager.login_as(email)
    return {"user": email, "lead": lead.name}


@frappe.whitelist(allow_guest=True)
def portal_login(email, password):
    email = (email or "").strip().lower()
    try:
        frappe.local.login_manager.authenticate(user=email, pwd=password)
        frappe.local.login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.throw(_("Incorrect email or password."))
    return {"user": frappe.session.user}


@frappe.whitelist()
def portal_logout():
    frappe.local.login_manager.logout()
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist(allow_guest=True)
def get_current_portal_user():
    if frappe.session.user == "Guest":
        return None
    user_doc = frappe.db.get_value("User", frappe.session.user, ["full_name", "phone", "portal_lead"], as_dict=True)
    phone = user_doc.phone
    if not phone and user_doc.portal_lead:
        phone = frappe.db.get_value("Lead", user_doc.portal_lead, "mobile_no")
    return {
        "user": frappe.session.user,
        "full_name": user_doc.full_name,
        "phone": phone,
    }


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


def _property_row_to_dict(row):
    """Standalone property (zero Units) shown as its own portal card, using
    the Property-level rent/bedrooms/bathrooms/etc fields instead of a Unit's.
    """
    return {
        "name": row.property,
        "unit_no": None,
        "unit_title": row.property_name,
        "floor": None,
        "unit_type": row.property_type,
        "usage": row.usage,
        "status": "Vacant",
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
        "is_standalone_property": 1,
    }


@frappe.whitelist(allow_guest=True)
def get_live_properties(location=None, unit_type=None, min_rent=None, max_rent=None,
                         bedrooms=None, start=0, page_length=12):
    """Returns published portal listings — either a Unit inside a building, or
    a standalone Property with zero Units (a whole villa/shop rented as one
    entity), using the Property-level rent/bedrooms/bathrooms/etc fields.
    A Unit only appears if BOTH itself (published_to_portal + status=Vacant)
    AND its parent Property (is_live) allow it. A standalone Property only
    appears if it has zero Units, is_live, published_to_portal, has no
    current_lease, and has annual_rent set — mirroring the Unit rules.
    NOTE: unit_type is a Unit-only field. Filtering by it excludes standalone
    properties entirely, since they have no equivalent attribute to match on.
    """
    values = {}
    unit_conditions = ["u.published_to_portal = 1", "u.status = 'Vacant'", "p.is_live = 1"]
    prop_conditions = ["p.is_live = 1", "p.published_to_portal = 1",
                        "(p.current_lease IS NULL OR p.current_lease = '')",
                        "p.annual_rent IS NOT NULL", "p.annual_rent > 0"]

    if location:
        loc_clause = ("(p.city = %(location)s OR p.area = %(location)s "
                       "OR CONCAT(p.area, ', ', p.city) = %(location)s)")
        unit_conditions.append(loc_clause)
        prop_conditions.append(loc_clause)
        values["location"] = location
    if min_rent:
        unit_conditions.append("u.annual_rent >= %(min_rent)s")
        prop_conditions.append("p.annual_rent >= %(min_rent)s")
        values["min_rent"] = min_rent
    if max_rent:
        unit_conditions.append("u.annual_rent <= %(max_rent)s")
        prop_conditions.append("p.annual_rent <= %(max_rent)s")
        values["max_rent"] = max_rent
    if bedrooms:
        unit_conditions.append("u.bedrooms >= %(bedrooms)s")
        prop_conditions.append("p.bedrooms >= %(bedrooms)s")
        values["bedrooms"] = bedrooms
    if unit_type:
        unit_conditions.append("u.unit_type = %(unit_type)s")
        values["unit_type"] = unit_type

    unit_rows = frappe.db.sql(f"""
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
            p.latitude, p.longitude, u.modified as sort_modified
        FROM `tabUnit` u
        INNER JOIN `tabProperty` p ON u.property = p.name
        WHERE {" AND ".join(unit_conditions)}
        ORDER BY u.modified DESC
        LIMIT 500
    """, values, as_dict=True)

    results = [_unit_row_to_dict(r) for r in unit_rows]
    for r, raw in zip(results, unit_rows):
        r["_sort_modified"] = raw.sort_modified

    if not unit_type:
        prop_rows = frappe.db.sql(f"""
            SELECT
                p.name as property, p.property_name, p.property_type, p.usage,
                p.furnishing, p.parking_slots, p.area_sqm, p.bedrooms, p.bathrooms,
                p.annual_rent, p.city, p.area,
                COALESCE(p.cover_image, (
                    SELECT pp.image FROM `tabProperty Photo` pp
                    WHERE pp.parent = p.name
                    ORDER BY pp.is_cover DESC, pp.idx ASC
                    LIMIT 1
                )) as cover_image,
                p.latitude, p.longitude, p.modified as sort_modified
            FROM `tabProperty` p
            LEFT JOIN `tabUnit` u2 ON u2.property = p.name
            WHERE u2.name IS NULL AND {" AND ".join(prop_conditions)}
            LIMIT 500
        """, values, as_dict=True)
        prop_results = [_property_row_to_dict(r) for r in prop_rows]
        for r, raw in zip(prop_results, prop_rows):
            r["_sort_modified"] = raw.sort_modified
        results += prop_results

    results.sort(key=lambda r: r.get("_sort_modified") or "", reverse=True)
    for r in results:
        r.pop("_sort_modified", None)

    start = int(start or 0)
    page_length = int(page_length or 12)
    return results[start:start + page_length]


@frappe.whitelist(allow_guest=True)
def get_property_detail(unit=None, property=None):
    """Full detail for a single dossier view — either a Unit, or a standalone
    Property with zero Units — including amenities (pulled from the parent
    Property's Table MultiSelect) and photos.
    """
    if unit:
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
        property_name = data["property"]
    elif property:
        row = frappe.db.sql("""
            SELECT
                p.name as property, p.property_name, p.property_type, p.usage,
                p.furnishing, p.parking_slots, p.area_sqm, p.bedrooms, p.bathrooms,
                p.annual_rent, p.city, p.area, p.address_line,
                COALESCE(p.cover_image, (
                    SELECT pp.image FROM `tabProperty Photo` pp
                    WHERE pp.parent = p.name
                    ORDER BY pp.is_cover DESC, pp.idx ASC
                    LIMIT 1
                )) as cover_image,
                p.latitude, p.longitude
            FROM `tabProperty` p
            WHERE p.name = %(property)s
        """, {"property": property}, as_dict=True)
        if not row:
            frappe.throw(_("Property not found or not published."))
        data = _property_row_to_dict(row[0])
        data["address_line"] = row[0].address_line
        property_name = data["property"]
    else:
        frappe.throw(_("Either unit or property is required."))

    # Amenities live on the parent Property as a Table MultiSelect
    amenities = frappe.get_all(
        "Property Amenity",
        filters={"parent": property_name, "parenttype": "Property"},
        pluck="amenity",
    )
    data["amenities"] = amenities

    # Photos child table on Property
    photos = frappe.get_all(
        "Property Photo",
        filters={"parent": property_name, "parenttype": "Property"},
        fields=["image", "caption", "is_cover"],
        order_by="is_cover desc",
    )
    data["photos"] = [p.image for p in photos]

    return data


@frappe.whitelist()
def toggle_wishlist(unit):
    identity = _get_identity_for_current_user()
    filters = {"unit": unit}
    if identity["customer"]:
        filters["customer"] = identity["customer"]
    else:
        filters["lead"] = identity["lead"]

    existing = frappe.db.exists("Property Wishlist", filters)
    if existing:
        frappe.delete_doc("Property Wishlist", existing, ignore_permissions=True)
        return {"saved": False}
    doc = frappe.get_doc({
        "doctype": "Property Wishlist",
        "customer": identity["customer"],
        "lead": identity["lead"],
        "unit": unit,
    })
    doc.insert(ignore_permissions=True)
    return {"saved": True}


@frappe.whitelist(allow_guest=True)
def submit_enquiry(unit, name=None, phone=None, message=None):
    customer = None
    lead = None
    if frappe.session.user != "Guest":
        lead = frappe.db.get_value("User", frappe.session.user, "portal_lead")
        customer = None

    doc = frappe.get_doc({
        "doctype": "Property Enquiry",
        "enquiry_id": frappe.model.naming.make_autoname("ENQ-.#####"),
        "unit": unit,
        "customer": customer,
        "linked_lead": lead,
        "enquiry_type": "General Enquiry",
        "message": message,
    })
    doc.insert(ignore_permissions=True)
    _notify_re_managers(
        document_type="Property Enquiry",
        document_name=doc.name,
        subject=_("New enquiry received for unit {0}").format(unit),
    )
    if lead:
        _get_or_create_re_lead(lead)

    recipient_email = frappe.session.user if frappe.session.user != "Guest" else None
    if not recipient_email and lead:
        recipient_email = frappe.db.get_value("Lead", lead, "email_id")
    if recipient_email:
        try:
            frappe.sendmail(
                recipients=recipient_email,
                subject=_("We received your enquiry"),
                message=_(
                    "Hi {0},<br><br>"
                    "Thanks for your enquiry about unit {1}. An agent will follow up with you shortly.<br><br>"
                    "— RE Core"
                ).format(name or "there", unit),
                now=True,
            )
        except Exception:
            frappe.log_error(title="Enquiry confirmation email failed", message=frappe.get_traceback())

    return {"name": doc.name}


@frappe.whitelist()
def book_site_visit(unit, visit_date, visit_time_slot):
    identity = _get_identity_for_current_user()
    doc = frappe.get_doc({
        "doctype": "Site Visit Booking",
        "unit": unit,
        "customer": identity["customer"],
        "lead": identity["lead"],
        "visit_date": visit_date,
        "visit_time_slot": visit_time_slot,
    })
    doc.insert(ignore_permissions=True)
    _notify_re_managers(
        document_type="Site Visit Booking",
        document_name=doc.name,
        subject=_("New site visit requested for unit {0}").format(unit),
    )
    if identity.get("lead"):
        _get_or_create_re_lead(identity["lead"])

    try:
        frappe.sendmail(
            recipients=frappe.session.user,
            subject=_("Site visit requested"),
            message=_(
                "Hi,<br><br>"
                "Your site visit for unit {0} is requested for {1} ({2}). "
                "You'll get a confirmation once an agent reviews it.<br><br>"
                "— RE Core"
            ).format(unit, visit_date, visit_time_slot),
            now=True,
        )
    except Exception:
        frappe.log_error(title="Site visit confirmation email failed", message=frappe.get_traceback())

    return {"name": doc.name}


def _get_or_create_re_lead(core_lead):
    """Find-or-create the RE Lead bridged from a portal-originated core Lead,
    so portal activity surfaces in the agent-facing CRM pipeline (re_crm).
    Reuses the same RE Lead across repeat submissions from the same visitor.
    Never throws - portal flows must not break if the CRM bridge has an issue.
    """
    if not core_lead:
        return None
    try:
        existing = frappe.db.get_value("RE Lead", {"portal_lead": core_lead}, "name")
        if existing:
            return existing

        lead_doc = frappe.get_doc("Lead", core_lead)
        re_lead = frappe.get_doc({
            "doctype": "RE Lead",
            "full_name": lead_doc.lead_name or "Portal Visitor",
            "mobile": lead_doc.mobile_no or "N/A",
            "email": lead_doc.email_id,
            "status": "New",
            "source": "Website",
            "request_source": "Portal",
            "portal_lead": core_lead,
        })
        re_lead.insert(ignore_permissions=True)
        return re_lead.name
    except Exception:
        frappe.log_error(title="RE Lead bridge failed", message=frappe.get_traceback())
        return None


def _notify_re_managers(document_type, document_name, subject):
    """Alert every enabled RE Manager about a new portal-originated record,
    matching the notification pattern used in Lease Contract._flag_security_deposit.
    """
    for user in frappe.get_all("Has Role", filters={"role": "RE Manager", "parenttype": "User"}, pluck="parent"):
        if frappe.db.get_value("User", user, "enabled"):
            frappe.get_doc({
                "doctype": "Notification Log",
                "for_user": user,
                "type": "Alert",
                "document_type": document_type,
                "document_name": document_name,
                "subject": subject,
            }).insert(ignore_permissions=True)


def _get_or_create_tenant_for_current_user():
    """Find-or-create a Tenant record for the logged-in portal user, using
    their Lead info (name/phone/email) the first time they request a lease.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please log in to do that."))

    existing = frappe.db.get_value("Tenant", {"portal_user": user}, "name")
    if existing:
        return existing

    lead_name = frappe.db.get_value("User", user, "portal_lead")
    if not lead_name:
        frappe.throw(_("No profile linked to this account."))
    lead = frappe.get_doc("Lead", lead_name)

    tenant = frappe.get_doc({
        "doctype": "Tenant",
        "tenant_name": lead.lead_name or lead.email_id,
        "mobile": lead.mobile_no or "N/A",
        "email": lead.email_id,
        "portal_user": user,
        "request_source": "Portal",
    })
    tenant.insert(ignore_permissions=True)
    return tenant.name


@frappe.whitelist()
def request_lease_contract(unit, start_date, duration_months):
    """Portal-originated lease request. Creates a Draft Lease Contract only -
    never submitted. Mirrors re_core.api.create_lease_contract but resolves
    tenant/property/rent from the unit + logged-in visitor automatically.
    """
    from frappe.utils import add_months, flt

    tenant = _get_or_create_tenant_for_current_user()

    unit_doc = frappe.db.get_value("Unit", unit, ["property", "annual_rent", "status"], as_dict=True)
    if not unit_doc:
        frappe.throw(_("Unit not found."))
    if unit_doc.status not in ("Vacant", "Reserved"):
        frappe.throw(_("This unit is no longer available."))
    if not unit_doc.annual_rent:
        frappe.throw(_("This unit has no rent set - please contact an agent."))

    duration_months = int(duration_months)
    end_date = add_months(start_date, duration_months)
    term_years = flt(duration_months) / 12
    term_total = flt(unit_doc.annual_rent) * term_years if term_years > 0 else flt(unit_doc.annual_rent)

    doc = frappe.get_doc({
        "doctype": "Lease Contract",
        "tenant": tenant,
        "unit": unit,
        "property": unit_doc.property,
        "start_date": start_date,
        "end_date": end_date,
        "payment_frequency": "Monthly",
        "status": "Draft",
        "request_source": "Portal",
        "charges": [{
            "charge_type": "Rent",
            "description": "Base Rent",
            "amount": term_total,
        }],
    })
    doc.insert(ignore_permissions=True)

    _notify_re_managers(
        "Lease Contract", doc.name,
        _("New lease request for unit {0}").format(unit)
    )
    core_lead = frappe.db.get_value("User", frappe.session.user, "portal_lead")
    if core_lead:
        _get_or_create_re_lead(core_lead)

    return {"name": doc.name}


@frappe.whitelist()
def get_my_requests():
    """Everything the logged-in portal visitor has submitted - enquiries,
    site visit requests, and lease requests - for their own 'My Requests' page.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please log in to view your requests."))

    lead = frappe.db.get_value("User", user, "portal_lead")
    tenant = frappe.db.get_value("Tenant", {"portal_user": user}, "name")

    enquiries = []
    visits = []
    leases = []

    if lead:
        enquiries = frappe.get_all(
            "Property Enquiry",
            filters={"linked_lead": lead},
            fields=["name", "unit", "property", "enquiry_type", "status", "message", "creation"],
            order_by="creation desc",
        )
        visits = frappe.get_all(
            "Site Visit Booking",
            filters={"lead": lead},
            fields=["name", "unit", "property", "visit_date", "visit_time_slot", "status", "creation"],
            order_by="creation desc",
        )

    if tenant:
        leases = frappe.get_all(
            "Lease Contract",
            filters={"tenant": tenant},
            fields=["name", "unit", "property", "start_date", "end_date", "status",
                     "docstatus", "total_contract_value", "creation"],
            order_by="creation desc",
        )

    all_units = list({r["unit"] for r in (enquiries + visits + leases) if r.get("unit")})
    unit_map = {
        u["name"]: u["unit_no"]
        for u in frappe.get_all("Unit", filters={"name": ["in", all_units]}, fields=["name", "unit_no"])
    } if all_units else {}
    for r in enquiries + visits + leases:
        r["unit_no"] = unit_map.get(r.get("unit"), r.get("unit"))

    return {"enquiries": enquiries, "visits": visits, "leases": leases}


def check_saved_searches():
    """Scheduled job (daily): for each enabled Saved Search, find units that
    became newly available since last_checked and match the criteria, notify
    the visitor by email + Notification Log, then advance last_checked.
    """
    searches = frappe.get_all(
        "Saved Search",
        filters={"enabled": 1},
        fields=["name", "lead", "location", "unit_type", "bedrooms", "min_rent", "max_rent", "last_checked"],
    )

    for s in searches:
        conditions = ["u.published_to_portal = 1", "u.status = 'Vacant'", "p.is_live = 1",
                      "u.modified > %(since)s"]
        values = {"since": s.last_checked}

        if s.location:
            conditions.append("(p.city = %(location)s OR p.area = %(location)s OR CONCAT(p.area, ', ', p.city) = %(location)s)")
            values["location"] = s.location
        if s.unit_type:
            conditions.append("u.unit_type = %(unit_type)s")
            values["unit_type"] = s.unit_type
        if s.bedrooms:
            conditions.append("u.bedrooms >= %(bedrooms)s")
            values["bedrooms"] = s.bedrooms
        if s.min_rent:
            conditions.append("u.annual_rent >= %(min_rent)s")
            values["min_rent"] = s.min_rent
        if s.max_rent:
            conditions.append("u.annual_rent <= %(max_rent)s")
            values["max_rent"] = s.max_rent

        matches = frappe.db.sql(f"""
            SELECT u.name as unit_name, u.unit_no, u.annual_rent, p.property_name, p.city, p.area
            FROM `tabUnit` u
            INNER JOIN `tabProperty` p ON u.property = p.name
            WHERE {" AND ".join(conditions)}
            LIMIT 20
        """, values, as_dict=True)

        if matches:
            _notify_saved_search_match(s, matches)

        frappe.db.set_value("Saved Search", s.name, "last_checked", frappe.utils.now())

    frappe.db.commit()


def _notify_saved_search_match(search, matches):
    lead_doc = frappe.get_doc("Lead", search.lead)
    user = frappe.db.get_value("User", {"portal_lead": search.lead}, "name")

    summary = ", ".join(f"{m.unit_no or m.unit_name} at {m.property_name}" for m in matches[:5])

    if user:
        frappe.get_doc({
            "doctype": "Notification Log",
            "for_user": user,
            "type": "Alert",
            "document_type": "Saved Search",
            "document_name": search.name,
            "subject": _("{0} new listing(s) match your saved search").format(len(matches)),
        }).insert(ignore_permissions=True)

    if lead_doc.email_id:
        try:
            frappe.sendmail(
                recipients=lead_doc.email_id,
                subject=_("New listings match your saved search"),
                message=_(
                    "Hi {0},<br><br>"
                    "{1} new listing(s) just became available matching your saved search:<br>{2}<br><br>"
                    "Log in to the portal to view and save them.<br><br>— RE Core"
                ).format(lead_doc.lead_name or "there", len(matches), summary),
                now=True,
            )
        except Exception:
            frappe.log_error(title="Saved search alert email failed", message=frappe.get_traceback())


@frappe.whitelist()
def create_saved_search(location=None, unit_type=None, bedrooms=None, min_rent=None, max_rent=None):
    identity = _get_identity_for_current_user()
    doc = frappe.get_doc({
        "doctype": "Saved Search",
        "lead": identity["lead"],
        "location": location,
        "unit_type": unit_type,
        "bedrooms": bedrooms,
        "min_rent": min_rent,
        "max_rent": max_rent,
        "last_checked": frappe.utils.now(),
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def get_my_saved_searches():
    identity = _get_identity_for_current_user()
    if not identity["lead"]:
        return []
    return frappe.get_all(
        "Saved Search",
        filters={"lead": identity["lead"]},
        fields=["name", "location", "unit_type", "bedrooms", "min_rent", "max_rent", "enabled", "creation"],
        order_by="creation desc",
    )


@frappe.whitelist()
def delete_saved_search(name):
    identity = _get_identity_for_current_user()
    owner_lead = frappe.db.get_value("Saved Search", name, "lead")
    if owner_lead != identity["lead"]:
        frappe.throw(_("Not permitted."))
    frappe.delete_doc("Saved Search", name, ignore_permissions=True)
    return {"deleted": name}


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
