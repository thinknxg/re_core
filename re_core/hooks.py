app_name = "re_core"
app_title = "RE Core"
app_publisher = "Kreatao"
app_description = "GCC Real Estate Platform — Property, Tenant & Lease Management"
app_email = "dev@kreatao.com"
app_license = "MIT"

required_apps = ["erpnext", "re_crm"]

after_install = "re_core.install.after_install"

fixtures = [
    {"doctype": "Custom Field", "filters": [
        ["dt", "in", ["Unit", "Tenant", "Property", "Purchase Invoice", "User", "RE Lead"]],
        ["fieldname", "in", [
            "published_to_portal",
            "portal_access_code",
            "ownership_section", "ownership_type", "column_break_ownership",
            "management_fee_type", "management_fee_value", "onetime_commission", "no_of_floors",
            "portal_section", "is_live", "published_on", "portal_visibility",
            "re_core_section", "custom_property", "custom_tenancy_id",
            "cb_re_core", "custom_sales_invoice_id", "custom_loan",
            "owner_ref", "custom_source_sales_invoice", "custom_lease_contract",
            "portal_lead", "request_source",
        ]],
    ]},
    {"dt": "Role", "filters": [["name", "in", [
        "RE Manager", "Property Manager", "Leasing Officer",
        "Maintenance Supervisor", "Tenant",
    ]]]},
    {"dt": "Workspace", "filters": [["name", "in", ["RE Core"]]]},
    {"dt": "Print Format", "filters": [["name", "in", [
        "Lease Contract Standard", "Tenant Rent Invoice",
    ]]]},
]

scheduler_events = {
    "daily": [
        "re_core.tasks.invoice_due_installments",
        "re_core.tasks.mark_overdue_installments",
        "re_core.tasks.lease_expiry_pipeline",
        "re_core.tasks.pdc_deposit_reminders",
        "re_core.tasks.document_expiry_alerts",
        "re_core.re_core.listing_portal_api.listing_portal.check_saved_searches",
    ],
}

permission_query_conditions = {
    "Lease Contract": "re_core.permissions.lease_contract_query",
    "Rent Schedule": "re_core.permissions.rent_schedule_query",
    "Post Dated Cheque": "re_core.permissions.pdc_query",
    "Security Deposit": "re_core.permissions.security_deposit_query",
    "Maintenance Request": "re_core.permissions.maintenance_request_query",
    "Tenant": "re_core.permissions.tenant_query",
}

has_permission = {
    "Lease Contract": "re_core.permissions.has_permission",
    "Rent Schedule": "re_core.permissions.has_permission",
    "Post Dated Cheque": "re_core.permissions.has_permission",
    "Security Deposit": "re_core.permissions.has_permission",
    "Maintenance Request": "re_core.permissions.has_permission",
    "Tenant": "re_core.permissions.has_permission",
}

doctype_js = {
"Property": "public/js/property_live_toggle.js",
"Unit": "public/js/unit_lease_contract.js"
}

doc_events = {
"Post Dated Cheque": {
"on_submit": "re_core.re_core.pdc_bank_sync.create_or_sync_payment_entry"
},
"Security Deposit": {
"on_submit": "re_core.re_core.security_deposit_accounting.create_deposit_journal_entry"
},
}
