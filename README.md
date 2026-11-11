# RE Core — GCC Real Estate Platform (Phase 1)

Property, Unit, Owner, Tenant and Lease lifecycle management on Frappe/ERPNext v16.
Single-site, Company-per-landlord multi-tenant model. OMR-first, GCC-ready (5% Oman VAT
via ERPNext tax templates; Ejari/RERA/Tawtheeq compliance fields).

## Included
- 19 DocTypes: Property, Unit, Property Owner, Tenant (+KYC child), Lease Contract (submittable),
  Lease Charge, Rent Schedule (+Rent Installment), Post Dated Cheque, Security Deposit,
  Maintenance Request, Maintenance Job, Move In Out Inspection (+Inspection Item),
  Utility Account, Amenity (+Property Amenity), Property Photo, Property Settings (Single)
- Lease submit → auto Rent Schedule, Security Deposit draft, optional PDC batch, unit status flip
- Daily schedulers: installment invoicing (ERPNext Sales Invoice), overdue dunning,
  lease expiry pipeline, PDC deposit reminders
- PDC lifecycle: Received → Deposited → Cleared (auto Payment Entry) / Bounced
- Tenant portal user provisioning (role: Tenant) with row-level permission query conditions
- Roles + Property Ops workspace shipped as fixtures

## Property Operations workspace (v16)
Standard workspaces shipped from the module folder (synced by `bench migrate`, no manual setup):
- **Property Operations** - main control panel: 10 Number Cards, 7 Dashboard Charts, 12 shortcuts,
  3 Quick Lists and six link sections. Visible to RE Manager, Property Manager, Leasing Officer,
  Accounts User, Maintenance Supervisor.
- **RE Finance** (Accounts User / managers) and **RE Maintenance** (Maintenance Supervisor / managers):
  focused dashboards reusing the same cards and charts.
- Sidebar: `fixtures/workspace_sidebar.json` (sections for Portfolio, Tenants, Leases, Collections,
  Maintenance, Reports, Settings). The original **RE Core** workspace remains as the hub for CRM,
  listings and portal.
- Reports: RE Outstanding Rent, RE Rent Collection, RE Lease Expiry, RE PDC Status, RE Maintenance
  Overview (plus the existing Rent Roll). Rent charts/reports resolve permitted Rent Schedules first, so
  company/user permissions and the Tenant row-level rule still apply.
Workspace visibility is not a substitute for document permissions; those stay unchanged.

## Install
```bash
bench get-app /path/to/re_core
bench --site yoursite.local install-app re_core
bench --site yoursite.local migrate
```

After install: open **Property Settings**, set the Rent Item (auto-created as "Rental Charge"),
invoice lead days, and (optionally) the Deposits Held liability account per your CoA.

## Regenerating DocType JSONs
```bash
python3 scripts/generate_doctypes.py
```
