#!/usr/bin/env python3
"""
re_core DocType JSON generator (Frappe/ERPNext v16).

Regenerates every DocType JSON under re_core/re_core/re_core/doctype/.
Controllers (.py) are hand-maintained and never overwritten by this script.

    python3 scripts/generate_doctypes.py
"""

import json
import os
import re

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE = "RE Core"
DOCTYPE_DIR = os.path.join(APP_ROOT, "re_core", "re_core", "doctype")
TS = "2026-01-01 00:00:00.000000"

# ---------------------------------------------------------------- helpers


def scrub(name: str) -> str:
    return re.sub(r"[\s-]+", "_", name.strip().lower())


def f(fieldname, fieldtype="Data", label=None, **kw):
    d = {
        "fieldname": fieldname,
        "fieldtype": fieldtype,
        "label": label or fieldname.replace("_", " ").title(),
    }
    d.update(kw)
    return d


def sb(fieldname, label=None, **kw):
    return f(fieldname, "Section Break", label or "", **kw)


def cb(i):
    return f(f"col_break_{i}", "Column Break", "")


def perm(role, **kw):
    base = {
        "role": role, "read": 1, "write": 1, "create": 1,
        "email": 1, "print": 1, "report": 1, "export": 1, "share": 1,
    }
    base.update(kw)
    return base


MANAGER_PERMS = [
    perm("RE Manager", delete=1, submit=1, cancel=1, amend=1),
    perm("System Manager", delete=1, submit=1, cancel=1, amend=1),
]


def dt(name, fields, autoname=None, is_submittable=0, istable=0, issingle=0,
       title_field=None, perms=None, track_changes=1, image_field=None,
       description=None, search_fields=None, states=None):
    doc = {
        "actions": [],
        "allow_rename": 0,
        "autoname": autoname or "",
        "creation": TS,
        "doctype": "DocType",
        "editable_grid": 1,
        "engine": "InnoDB",
        "field_order": [x["fieldname"] for x in fields],
        "fields": fields,
        "index_web_pages_for_search": 0,
        "is_submittable": is_submittable,
        "issingle": issingle,
        "istable": istable,
        "links": [],
        "modified": TS,
        "modified_by": "Administrator",
        "module": MODULE,
        "name": name,
        "naming_rule": "Expression" if (autoname or "").startswith("format:") else "",
        "owner": "Administrator",
        "permissions": [] if istable else (perms if perms is not None else MANAGER_PERMS),
        "sort_field": "modified",
        "sort_order": "DESC",
        "states": states or [],
        "track_changes": track_changes,
    }
    if title_field:
        doc["title_field"] = title_field
    if image_field:
        doc["image_field"] = image_field
    if description:
        doc["description"] = description
    if search_fields:
        doc["search_fields"] = search_fields

    folder = os.path.join(DOCTYPE_DIR, scrub(name))
    os.makedirs(folder, exist_ok=True)
    init = os.path.join(folder, "__init__.py")
    if not os.path.exists(init):
        open(init, "w").close()
    with open(os.path.join(folder, f"{scrub(name)}.json"), "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"  wrote {name}")


def state(title, color, docstatus=0):
    return {"title": title, "color": color, "custom": 0}


# ---------------------------------------------------------------- masters

def gen_amenity():
    dt("Amenity",
       autoname="field:amenity_name",
       fields=[
           f("amenity_name", "Data", reqd=1, unique=1),
           f("icon", "Data", description="Optional icon class / emoji for portal display"),
       ],
       perms=[perm("RE Manager", delete=1), perm("Property Manager"),
              perm("Leasing Officer", write=0, create=0)])


def gen_property_amenity():
    dt("Property Amenity", istable=1, fields=[
        f("amenity", "Link", options="Amenity", reqd=1, in_list_view=1),
    ])


def gen_property_photo():
    dt("Property Photo", istable=1, fields=[
        f("image", "Attach Image", reqd=1, in_list_view=1),
        f("caption", "Data", in_list_view=1),
        f("is_cover", "Check", label="Cover Photo"),
    ])


def gen_property_owner():
    dt("Property Owner",
       autoname="format:OWN-{####}",
       title_field="owner_name",
       search_fields="owner_name,mobile",
       fields=[
           sb("details_sb", "Owner Details"),
           f("owner_name", "Data", reqd=1, in_list_view=1),
           f("owner_type", "Select", options="\nIndividual\nCompany", default="Individual"),
           f("mobile", "Data", options="Phone", in_list_view=1),
           f("email", "Data", options="Email"),
           cb(1),
           f("company", "Link", options="Company", reqd=1, in_standard_filter=1,
             description="ERPNext Company that owns this landlord's financials"),
           f("supplier", "Link", options="Supplier",
             description="Supplier record used for owner payouts"),
           f("management_fee_percent", "Percent", label="Management Fee %", default=5),
           sb("kyc_sb", "Identification"),
           f("national_id", "Data", label="National ID / CR Number"),
           f("id_expiry", "Date", label="ID / CR Expiry"),
           cb(2),
           f("bank_name", "Data"),
           f("iban", "Data", label="IBAN"),
           sb("notes_sb", ""),
           f("notes", "Small Text"),
       ],
       perms=[perm("RE Manager", delete=1), perm("Property Manager"),
              perm("Accounts User", write=0, create=0)])


def gen_property():
    gcc = "\nOman\nUnited Arab Emirates\nSaudi Arabia\nBahrain\nQatar\nKuwait"
    dt("Property",
       autoname="format:PROP-{YYYY}-{####}",
       title_field="property_name",
       image_field="cover_image",
       search_fields="property_name,city,area",
       fields=[
           sb("basic_sb", "Property"),
           f("property_name", "Data", reqd=1, in_list_view=1),
           f("property_type", "Select", reqd=1, in_standard_filter=1,
             options="\nApartment Building\nVilla\nVilla Compound\nCommercial Tower\nMixed Use\nLand"),
           f("status", "Select", default="Active", in_standard_filter=1,
             options="Active\nUnder Development\nSold\nArchived"),
           cb(1),
           f("owner_ref", "Link", options="Property Owner", label="Owner", reqd=1, in_list_view=1),
           f("company", "Link", options="Company", read_only=1,
             fetch_from="owner_ref.company", in_standard_filter=1),
           f("total_units", "Int", read_only=1),
           sb("addr_sb", "Location"),
           f("country", "Select", options=gcc, default="Oman", reqd=1),
           f("city", "Data", default="Muscat", in_list_view=1),
           f("area", "Data", label="Area / Wilaya", in_standard_filter=1),
           f("address_line", "Small Text", label="Address"),
           cb(2),
           f("latitude", "Float", precision=6),
           f("longitude", "Float", precision=6),
           sb("compliance_sb", "Compliance", collapsible=1),
           f("municipality_ref", "Data", label="Municipality Reference"),
           f("ejari_number", "Data", label="Ejari Number",
             depends_on="eval:doc.country=='United Arab Emirates'"),
           cb(3),
           f("rera_permit", "Data", label="RERA Permit",
             depends_on="eval:doc.country=='United Arab Emirates'"),
           f("tawtheeq_ref", "Data", label="Tawtheeq Reference",
             depends_on="eval:doc.country=='United Arab Emirates'"),
           sb("media_sb", "Media & Amenities", collapsible=1),
           f("cover_image", "Attach Image"),
           f("photos", "Table", options="Property Photo"),
           f("amenities", "Table MultiSelect", options="Property Amenity"),
           sb("notes_sb", "", collapsible=1),
           f("notes", "Text Editor"),
       ],
       perms=[perm("RE Manager", delete=1), perm("Property Manager"),
              perm("Leasing Officer", write=0, create=0),
              perm("Maintenance Supervisor", write=0, create=0)])


def gen_unit():
    dt("Unit",
       autoname="format:UNIT-{#####}",
       title_field="unit_title",
       search_fields="unit_no,property",
       fields=[
           sb("basic_sb", "Unit"),
           f("property", "Link", options="Property", reqd=1, in_list_view=1, in_standard_filter=1),
           f("unit_no", "Data", reqd=1, in_list_view=1),
           f("unit_title", "Data", read_only=1, hidden=1),
           f("floor", "Data"),
           cb(1),
           f("unit_type", "Select", reqd=1, in_standard_filter=1,
             options="\nStudio\n1BR\n2BR\n3BR\n4BR+\nPenthouse\nShop\nOffice\nWarehouse"),
           f("usage", "Select", options="Residential\nCommercial", default="Residential",
             description="Drives VAT treatment: Oman residential leases are VAT-exempt"),
           f("status", "Select", default="Vacant", in_list_view=1, in_standard_filter=1,
             read_only=1, options="Vacant\nReserved\nOccupied\nUnder Maintenance\nBlocked"),
           sb("specs_sb", "Specifications"),
           f("area_sqm", "Float", label="Area (sqm)"),
           f("bedrooms", "Int"),
           f("bathrooms", "Int"),
           cb(2),
           f("furnishing", "Select", options="Unfurnished\nSemi Furnished\nFully Furnished",
             default="Unfurnished"),
           f("parking_slots", "Int"),
           sb("fin_sb", "Financials"),
           f("annual_rent", "Currency", label="Asking Annual Rent"),
           cb(3),
           f("current_lease", "Link", options="Lease Contract", read_only=1),
           f("company", "Link", options="Company", read_only=1, fetch_from="property.company"),
       ],
       perms=[perm("RE Manager", delete=1), perm("Property Manager"),
              perm("Leasing Officer", write=0, create=0),
              perm("Maintenance Supervisor", write=0, create=0)])


def gen_tenant_kyc():
    dt("Tenant KYC Document", istable=1, fields=[
        f("id_type", "Select", reqd=1, in_list_view=1,
          options="\nNational ID\nResident Card\nPassport\nVisa\nCR License\nOther"),
        f("id_number", "Data", reqd=1, in_list_view=1),
        f("expiry_date", "Date", in_list_view=1),
        f("attachment", "Attach", in_list_view=1),
    ])


def gen_tenant():
    dt("Tenant",
       autoname="format:TEN-{#####}",
       title_field="tenant_name",
       search_fields="tenant_name,mobile,email",
       fields=[
           sb("basic_sb", "Tenant"),
           f("tenant_name", "Data", reqd=1, in_list_view=1),
           f("tenant_type", "Select", options="\nIndividual\nCompany", default="Individual"),
           f("nationality", "Data"),
           cb(1),
           f("mobile", "Data", options="Phone", reqd=1, in_list_view=1),
           f("email", "Data", options="Email"),
           f("whatsapp_number", "Data", options="Phone",
             description="Defaults to mobile if left blank"),
           sb("links_sb", "Accounts"),
           f("customer", "Link", options="Customer", read_only=1,
             description="Auto-created on save; all rent invoices post against this Customer"),
           cb(2),
           f("enable_portal", "Check", label="Enable Tenant Portal", default=0),
           f("portal_user", "Link", options="User", read_only=1),
           sb("kyc_sb", "KYC Documents"),
           f("kyc_documents", "Table", options="Tenant KYC Document"),
           sb("emergency_sb", "Emergency Contact", collapsible=1),
           f("emergency_contact_name", "Data"),
           f("emergency_contact_mobile", "Data", options="Phone"),
           sb("status_sb", ""),
           f("disabled", "Check"),
       ],
       perms=[perm("RE Manager", delete=1), perm("Property Manager"), perm("Leasing Officer"),
              perm("Tenant", write=0, create=0, email=0, print=0, report=0, export=0, share=0,
                   if_owner=0)])


def gen_utility_account():
    dt("Utility Account",
       autoname="format:UTIL-{#####}",
       fields=[
           f("unit", "Link", options="Unit", reqd=1, in_list_view=1),
           f("utility_type", "Select", reqd=1, in_list_view=1,
             options="\nElectricity\nWater\nGas\nInternet\nOther"),
           f("provider", "Data", description="e.g. Nama, Muscat Electricity, Oman Water"),
           f("account_number", "Data", reqd=1, in_list_view=1),
           f("meter_number", "Data"),
           f("in_tenant_name", "Check", label="Registered in Tenant Name"),
       ],
       perms=[perm("RE Manager", delete=1), perm("Property Manager"),
              perm("Maintenance Supervisor")])


# ---------------------------------------------------------------- leasing

def gen_lease_charge():
    dt("Lease Charge", istable=1, fields=[
        f("charge_type", "Select", reqd=1, in_list_view=1,
          options="\nRent\nService Charge\nParking\nFurniture\nUtilities\nOther"),
        f("description", "Data", in_list_view=1),
        f("amount", "Currency", reqd=1, in_list_view=1,
          description="Total for the full lease term"),
        f("item_tax_template", "Link", options="Item Tax Template", in_list_view=1,
          description="Leave blank for exempt (e.g. Oman residential rent)"),
    ])


def gen_lease_contract():
    dt("Lease Contract",
       autoname="format:LEASE-{YYYY}-{####}",
       is_submittable=1,
       title_field="title",
       search_fields="tenant,unit,property",
       fields=[
           sb("parties_sb", "Parties"),
           f("title", "Data", read_only=1, hidden=1),
           f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1, in_standard_filter=1),
           f("tenant_name", "Data", fetch_from="tenant.tenant_name", read_only=1),
           cb(1),
           f("unit", "Link", options="Unit", reqd=1, in_list_view=1),
           f("property", "Link", options="Property", fetch_from="unit.property",
             read_only=1, in_standard_filter=1),
           f("owner_ref", "Link", options="Property Owner", label="Owner",
             fetch_from="property.owner_ref", read_only=1),
           f("company", "Link", options="Company", fetch_from="property.company",
             read_only=1, in_standard_filter=1),
           sb("term_sb", "Term"),
           f("start_date", "Date", reqd=1, in_list_view=1),
           f("end_date", "Date", reqd=1),
           f("duration_months", "Int", read_only=1),
           cb(2),
           f("notice_period_days", "Int", default=60),
           f("auto_renew", "Check", label="Auto-Renew Offer"),
           f("status", "Select", read_only=1, default="Draft", in_standard_filter=1,
             options="Draft\nActive\nExpiring\nExpired\nTerminated\nRenewed"),
           sb("fin_sb", "Financials"),
           f("charges", "Table", options="Lease Charge", reqd=1),
           f("total_contract_value", "Currency", read_only=1, in_list_view=1),
           cb(3),
           f("payment_frequency", "Select", reqd=1, default="Quarterly",
             options="Annual\nSemi-Annual\nQuarterly\nMonthly\nCustom"),
           f("custom_installments", "Int", label="Number of Cheques",
             depends_on="eval:doc.payment_frequency=='Custom'",
             mandatory_depends_on="eval:doc.payment_frequency=='Custom'"),
           f("security_deposit_amount", "Currency"),
           f("broker_commission", "Currency"),
           sb("compliance_sb", "Compliance", collapsible=1),
           f("ejari_contract_no", "Data", label="Ejari Contract No"),
           f("municipality_attestation", "Attach"),
           f("signed_contract", "Attach", label="Signed Contract Copy"),
           sb("gen_sb", "Generated Documents", collapsible=1),
           f("rent_schedule", "Link", options="Rent Schedule", read_only=1),
           f("security_deposit", "Link", options="Security Deposit", read_only=1),
           sb("term_notes_sb", "", collapsible=1),
           f("terms", "Text Editor", label="Terms & Conditions"),
           f("amended_from", "Link", options="Lease Contract", read_only=1, no_copy=1,
             print_hide=1),
       ],
       perms=[perm("RE Manager", delete=1, submit=1, cancel=1, amend=1),
              perm("Property Manager", submit=1, cancel=1, amend=1),
              perm("Leasing Officer", submit=1),
              perm("Accounts User", write=0, create=0),
              perm("Tenant", write=0, create=0, email=0, report=0, export=0, share=0)])


def gen_rent_installment():
    dt("Rent Installment", istable=1, fields=[
        f("installment_no", "Int", label="No", in_list_view=1, read_only=1),
        f("due_date", "Date", reqd=1, in_list_view=1),
        f("amount", "Currency", reqd=1, in_list_view=1),
        f("status", "Select", default="Pending", in_list_view=1,
          options="Pending\nInvoiced\nPaid\nOverdue\nBounced\nCancelled"),
        f("pdc", "Link", options="Post Dated Cheque", label="PDC", in_list_view=1),
        f("sales_invoice", "Link", options="Sales Invoice", read_only=1, in_list_view=1),
        f("remarks", "Data"),
    ])


def gen_rent_schedule():
    dt("Rent Schedule",
       autoname="format:RS-{#####}",
       search_fields="lease_contract,tenant",
       fields=[
           f("lease_contract", "Link", options="Lease Contract", reqd=1, read_only=1,
             in_list_view=1),
           f("tenant", "Link", options="Tenant", fetch_from="lease_contract.tenant",
             read_only=1, in_list_view=1, in_standard_filter=1),
           f("company", "Link", options="Company", fetch_from="lease_contract.company",
             read_only=1),
           f("status", "Select", default="Active", read_only=1, in_standard_filter=1,
             options="Active\nCompleted\nCancelled"),
           sb("inst_sb", "Installments"),
           f("installments", "Table", options="Rent Installment"),
           f("total_amount", "Currency", read_only=1),
       ],
       perms=[perm("RE Manager", delete=1), perm("Property Manager"),
              perm("Leasing Officer", write=0, create=0), perm("Accounts User"),
              perm("Tenant", write=0, create=0, email=0, report=0, export=0, share=0)])


def gen_pdc():
    dt("Post Dated Cheque",
       autoname="format:PDC-{#####}",
       is_submittable=1,
       search_fields="cheque_no,tenant,bank",
       fields=[
           sb("cheque_sb", "Cheque"),
           f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1, in_standard_filter=1),
           f("lease_contract", "Link", options="Lease Contract"),
           f("company", "Link", options="Company", fetch_from="lease_contract.company",
             read_only=1),
           cb(1),
           f("cheque_no", "Data", reqd=1, in_list_view=1),
           f("bank", "Data", reqd=1),
           f("cheque_date", "Date", reqd=1, in_list_view=1),
           f("amount", "Currency", reqd=1, in_list_view=1),
           sb("status_sb", "Lifecycle"),
           f("status", "Select", default="Received", read_only=1, in_list_view=1,
             in_standard_filter=1, allow_on_submit=1,
             options="Received\nDeposited\nCleared\nBounced\nReplaced\nReturned"),
           f("deposit_date", "Date", allow_on_submit=1, read_only=1),
           f("clearance_date", "Date", allow_on_submit=1, read_only=1),
           cb(2),
           f("deposit_account", "Link", options="Account",
             description="Bank account the cheque is deposited into"),
           f("payment_entry", "Link", options="Payment Entry", read_only=1,
             allow_on_submit=1, no_copy=1),
           f("bounce_reason", "Small Text", allow_on_submit=1, read_only=1),
           f("amended_from", "Link", options="Post Dated Cheque", read_only=1, no_copy=1,
             print_hide=1),
       ],
       perms=[perm("RE Manager", delete=1, submit=1, cancel=1, amend=1),
              perm("Accounts User", submit=1, cancel=1, amend=1),
              perm("Property Manager", write=0, create=0),
              perm("Tenant", write=0, create=0, email=0, report=0, export=0, share=0)])


def gen_security_deposit():
    dt("Security Deposit",
       autoname="format:SD-{#####}",
       is_submittable=1,
       fields=[
           sb("dep_sb", "Deposit"),
           f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1),
           f("lease_contract", "Link", options="Lease Contract", reqd=1, in_list_view=1),
           f("company", "Link", options="Company", fetch_from="lease_contract.company",
             read_only=1),
           cb(1),
           f("amount", "Currency", reqd=1, in_list_view=1),
           f("received_date", "Date"),
           f("status", "Select", default="Held", read_only=1, in_list_view=1,
             in_standard_filter=1, allow_on_submit=1,
             options="Draft\nHeld\nPartially Refunded\nRefunded\nForfeited"),
           sb("refund_sb", "Refund / Forfeit", collapsible=1),
           f("deduction_amount", "Currency", allow_on_submit=1),
           f("deduction_reason", "Small Text", allow_on_submit=1),
           f("refunded_amount", "Currency", read_only=1, allow_on_submit=1),
           cb(2),
           f("journal_entry", "Link", options="Journal Entry", read_only=1,
             allow_on_submit=1, no_copy=1),
           f("refund_payment_entry", "Link", options="Payment Entry", read_only=1,
             allow_on_submit=1, no_copy=1),
           f("amended_from", "Link", options="Security Deposit", read_only=1, no_copy=1,
             print_hide=1),
       ],
       perms=[perm("RE Manager", delete=1, submit=1, cancel=1, amend=1),
              perm("Accounts User", submit=1, cancel=1, amend=1),
              perm("Property Manager", write=0, create=0),
              perm("Tenant", write=0, create=0, email=0, report=0, export=0, share=0)])


# ---------------------------------------------------------------- maintenance

def gen_maintenance_request():
    dt("Maintenance Request",
       autoname="format:MR-{YYYY}-{####}",
       search_fields="unit,category,status",
       fields=[
           sb("req_sb", "Request"),
           f("unit", "Link", options="Unit", reqd=1, in_list_view=1),
           f("property", "Link", options="Property", fetch_from="unit.property",
             read_only=1, in_standard_filter=1),
           f("tenant", "Link", options="Tenant",
             description="Set automatically for portal-raised requests"),
           cb(1),
           f("category", "Select", reqd=1, in_list_view=1, in_standard_filter=1,
             options="\nPlumbing\nElectrical\nAC\nCivil\nAppliances\nPest Control\nOther"),
           f("priority", "Select", options="Low\nMedium\nHigh\nEmergency",
             default="Medium", in_list_view=1),
           f("status", "Select", default="Open", in_list_view=1, in_standard_filter=1,
             options="Open\nIn Progress\nOn Hold\nCompleted\nRejected\nCancelled"),
           sb("desc_sb", "Details"),
           f("description", "Text", reqd=1),
           f("photo_1", "Attach Image"),
           f("photo_2", "Attach Image"),
           sb("job_sb", ""),
           f("maintenance_job", "Link", options="Maintenance Job", read_only=1),
           f("resolution_notes", "Small Text"),
       ],
       perms=[perm("RE Manager", delete=1), perm("Property Manager"),
              perm("Maintenance Supervisor"),
              perm("Tenant", write=0, create=1, email=0, report=0, export=0, share=0)])


def gen_maintenance_job():
    dt("Maintenance Job",
       autoname="format:MJ-{#####}",
       is_submittable=1,
       fields=[
           sb("job_sb", "Job"),
           f("maintenance_request", "Link", options="Maintenance Request", reqd=1,
             in_list_view=1),
           f("unit", "Link", options="Unit", fetch_from="maintenance_request.unit",
             read_only=1, in_list_view=1),
           f("company", "Link", options="Company", read_only=1),
           cb(1),
           f("assigned_type", "Select", options="Employee\nSupplier", default="Employee"),
           f("employee", "Link", options="Employee",
             depends_on="eval:doc.assigned_type=='Employee'"),
           f("supplier", "Link", options="Supplier",
             depends_on="eval:doc.assigned_type=='Supplier'"),
           f("scheduled_date", "Date", in_list_view=1),
           sb("cost_sb", "Costs"),
           f("material_cost", "Currency"),
           f("labor_cost", "Currency"),
           f("total_cost", "Currency", read_only=1, in_list_view=1),
           cb(2),
           f("billable_to", "Select", options="Owner\nTenant\nCompany", default="Owner"),
           f("purchase_invoice", "Link", options="Purchase Invoice", read_only=1,
             allow_on_submit=1, no_copy=1),
           f("sales_invoice", "Link", options="Sales Invoice", read_only=1,
             allow_on_submit=1, no_copy=1),
           sb("completion_sb", "Completion"),
           f("completion_date", "Date"),
           f("work_notes", "Small Text"),
           f("amended_from", "Link", options="Maintenance Job", read_only=1, no_copy=1,
             print_hide=1),
       ],
       perms=[perm("RE Manager", delete=1, submit=1, cancel=1, amend=1),
              perm("Maintenance Supervisor", submit=1),
              perm("Property Manager", submit=1, cancel=1)])


def gen_inspection_item():
    dt("Inspection Item", istable=1, fields=[
        f("room", "Data", reqd=1, in_list_view=1),
        f("item", "Data", reqd=1, in_list_view=1),
        f("condition", "Select", reqd=1, in_list_view=1,
          options="\nGood\nFair\nDamaged\nMissing"),
        f("photo", "Attach Image", in_list_view=1),
        f("remarks", "Data"),
    ])


def gen_inspection():
    dt("Move In Out Inspection",
       autoname="format:INSP-{#####}",
       is_submittable=1,
       fields=[
           sb("insp_sb", "Inspection"),
           f("inspection_type", "Select", reqd=1, options="\nMove In\nMove Out",
             in_list_view=1, in_standard_filter=1),
           f("lease_contract", "Link", options="Lease Contract", reqd=1, in_list_view=1),
           f("unit", "Link", options="Unit", fetch_from="lease_contract.unit", read_only=1),
           cb(1),
           f("inspection_date", "Date", reqd=1, in_list_view=1),
           f("inspected_by", "Link", options="User"),
           f("tenant_present", "Check"),
           sb("items_sb", "Checklist"),
           f("items", "Table", options="Inspection Item"),
           sb("outcome_sb", "Outcome"),
           f("estimated_damage_cost", "Currency",
             description="Feeds Security Deposit deductions on Move Out"),
           f("summary", "Small Text"),
           f("tenant_signature", "Attach Image"),
           f("amended_from", "Link", options="Move In Out Inspection", read_only=1,
             no_copy=1, print_hide=1),
       ],
       perms=[perm("RE Manager", delete=1, submit=1, cancel=1, amend=1),
              perm("Property Manager", submit=1, cancel=1),
              perm("Maintenance Supervisor", submit=1),
              perm("Tenant", write=0, create=0, email=0, report=0, export=0, share=0)])


# ---------------------------------------------------------------- settings

def gen_property_settings():
    dt("Property Settings",
       issingle=1,
       fields=[
           sb("invoicing_sb", "Invoicing"),
           f("rent_item", "Link", options="Item", reqd=1,
             description="Non-stock service item used on rent Sales Invoices"),
           f("invoice_lead_days", "Int", default=7,
             description="Create the Sales Invoice this many days before the installment due date"),
           cb(1),
           f("auto_create_pdcs", "Check", label="Draft PDCs on Lease Submit"),
           f("overdue_grace_days", "Int", default=3),
           sb("deposit_sb", "Security Deposits"),
           f("deposit_liability_account", "Link", options="Account",
             description="Deposits Held liability account; leave blank to skip Journal Entries"),
           cb(2),
           f("deposit_bank_account", "Link", options="Account",
             label="Deposit Receipt Account"),
           sb("expiry_sb", "Lease Expiry Pipeline"),
           f("expiring_flag_days", "Int", default=90,
             description="Mark lease as Expiring this many days before end date"),
           f("renewal_todo_days", "Int", default=60,
             description="Create a renewal follow-up ToDo this many days before end date"),
           sb("portal_sb", "Tenant Portal"),
           f("welcome_email_template", "Link", options="Email Template"),
       ],
       perms=[perm("RE Manager", delete=0), perm("System Manager")])


# ---------------------------------------------------------------- main

ALL = [
    gen_amenity, gen_property_amenity, gen_property_photo, gen_property_owner,
    gen_property, gen_unit, gen_tenant_kyc, gen_tenant, gen_utility_account,
    gen_lease_charge, gen_lease_contract, gen_rent_installment, gen_rent_schedule,
    gen_pdc, gen_security_deposit, gen_maintenance_request, gen_maintenance_job,
    gen_inspection_item, gen_inspection, gen_property_settings,
]

if __name__ == "__main__":
    os.makedirs(DOCTYPE_DIR, exist_ok=True)
    init = os.path.join(DOCTYPE_DIR, "__init__.py")
    if not os.path.exists(init):
        open(init, "w").close()
    print(f"Generating {len(ALL)} DocTypes into {DOCTYPE_DIR}")
    for gen in ALL:
        gen()
    print("Done.")
