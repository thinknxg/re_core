"""Demo-data exporter / loader for the RE platform.

Export (local, writes JSON + public images into this package):
    bench --site mysite-v16.localhost execute re_core.demo_data.tools.export_data
Load (cloud / scratch site; safe to repeat, existing records are skipped):
    bench --site SITE execute re_core.demo_data.tools.load_data --kwargs "{'dry_run': 1}"
    bench --site SITE execute re_core.demo_data.tools.load_data --kwargs "{'company': 'My Company'}"

Not exported on purpose: users and passwords, API keys, portal access codes, private files,
accounting records (invoices, payments, journal entries), chat/WhatsApp/voice logs, tenant portal
sessions, and rows that the apps seed themselves on install (amenities, lead sources, voice commands).
Personal fields are replaced by deterministic fake values (same input -> same fake value).
"""
import copy
import hashlib
import json
import os
import re
import shutil
from decimal import Decimal

import frappe

MASTERS = ("Supplier", "Customer", "Lead")  # exported only when an RE record links to them
DATA_ORDER = [
    "Property Owner", "Property", "Unit", "Utility Account", "Property Document", "Tenant",
    "RE Agent", "RE Lead", "Lease Contract", "Rent Schedule", "Security Deposit",
    "Post Dated Cheque", "Rent Credit Balance", "Expense Property", "Owner Statement",
    "Maintenance Request", "Move In Out Inspection", "Tenancy Bulk Payment", "RE Deal",
    "Reservation", "Site Visit", "Commission Entry", "Listing", "Listing Inquiry",
    "Property Enquiry", "Saved Search", "Property Wishlist", "Site Visit Booking",
]

# field name -> kind of fake value
FAKE_FIELDS = {"mobile": "mobile", "client_mobile": "mobile", "mobile_no": "mobile", "phone": "mobile",
               "email": "email", "email_id": "email", "id_number": "idnum", "account_number": "acct"}
# real names that must not reach git: exact word -> replacement (edit before exporting)
NAME_MAP = {"khabeer": "Khalid Al Harthy", "Sanjay": "Salim Al Rawahi"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

DROP_KEYS = {"creation", "modified", "modified_by", "owner", "_user_tags", "_comments", "_assign",
             "_liked_by", "_seen"}
CHILD_DROP = {"name", "parent", "parenttype", "parentfield"}
MAX_FILE = 1_500_000  # bytes; larger public files are not copied
# links to these are always cleared on load (accounting / bank records belong to the target site)
BLANK_ALWAYS = {"Journal Entry", "Purchase Invoice", "Sales Invoice", "Payment Entry",
                "Bank Account", "Account", "Cost Center"}
FALLBACK_FIRST = {"Customer Group": {"is_group": 0}, "Territory": {"is_group": 0},
                  "Supplier Group": {"is_group": 0}}


# ------------------------------------------------------------------ helpers

def _dir(*parts):
    return os.path.join(frappe.get_app_path("re_core"), "demo_data", *parts)


def _json_default(o):
    return float(o) if isinstance(o, Decimal) else str(o)


def _fake(kind, value):
    h = int(hashlib.sha256(value.strip().lower().encode()).hexdigest(), 16)
    if kind == "mobile":
        return f"+9689{h % 10**7:07d}"
    if kind == "email":
        return f"user{h % 10**8:08d}@example.com"
    if kind == "idnum":
        return f"ID{h % 10**7:07d}"
    return f"AC{h % 10**8:08d}"


def _records(rec):
    """The record itself and every nested child row."""
    yield rec
    for v in rec.values():
        if isinstance(v, list):
            for c in v:
                if isinstance(c, dict):
                    yield from _records(c)


def _clean(row, is_child=False):
    meta = frappe.get_meta(row["doctype"])
    passwords = {f.fieldname for f in meta.fields if f.fieldtype == "Password"}
    out = {}
    for k, v in row.items():
        if k.startswith("__") or k in DROP_KEYS or k in passwords or (is_child and k in CHILD_DROP):
            continue
        out[k] = [_clean(c, True) for c in v] if isinstance(v, list) else v
    return out


def _collect_fakes(docs_by_dt):
    found = {}
    for rows in docs_by_dt.values():
        for row in rows:
            for rec in _records(row):
                for k, v in rec.items():
                    if isinstance(v, str):
                        if k in FAKE_FIELDS and len(v.strip()) >= 6:
                            found[v] = _fake(FAKE_FIELDS[k], v)
                        for m in EMAIL_RE.findall(v):
                            if not m.lower().endswith("@example.com"):
                                found[m] = _fake("email", m)
    return found


def _apply(obj, fakes, name_res):
    if isinstance(obj, dict):
        return {k: _apply(v, fakes, name_res) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply(v, fakes, name_res) for v in obj]
    if isinstance(obj, str):
        for orig in sorted(fakes, key=len, reverse=True):
            if orig in obj:
                obj = obj.replace(orig, fakes[orig])
        for rx, new in name_res:
            obj = rx.sub(new, obj)
    return obj


def _attach_fields(doctype):
    return [f.fieldname for f in frappe.get_meta(doctype).fields
            if f.fieldtype in ("Attach", "Attach Image")]


def _handle_files(rec, report, files_dir):
    for f in _attach_fields(rec["doctype"]):
        v = rec.get(f)
        if not v:
            continue
        if isinstance(v, str) and v.startswith("/files/") and v.count("/") == 2:
            src = frappe.get_site_path("public", v.lstrip("/"))
            if os.path.isfile(src) and os.path.getsize(src) <= MAX_FILE:
                shutil.copy2(src, os.path.join(files_dir, os.path.basename(src)))
                report["copied"].append(v)
                continue
        rec.pop(f, None)
        report["blanked"].append(f"{rec['doctype']}.{f}")
    for val in list(rec.values()):
        if isinstance(val, list):
            for c in val:
                if isinstance(c, dict):
                    _handle_files(c, report, files_dir)


# ------------------------------------------------------------------ export

def export_data():
    data_dir, files_dir = _dir("data"), _dir("files")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(files_dir, exist_ok=True)
    docs = {}
    for dt in DATA_ORDER:
        if not frappe.db.exists("DocType", dt):
            continue
        names = frappe.get_all(dt, pluck="name", order_by="creation asc")
        if names:
            docs[dt] = [_clean(frappe.get_doc(dt, n).as_dict(no_nulls=True)) for n in names]

    wanted = {m: set() for m in MASTERS}
    for rows in docs.values():
        for row in rows:
            for rec in _records(row):
                for f in frappe.get_meta(rec["doctype"]).get_link_fields():
                    if f.options in MASTERS and rec.get(f.fieldname):
                        wanted[f.options].add(rec[f.fieldname])
    ordered = {}
    for m in MASTERS:
        names = [n for n in sorted(wanted[m]) if frappe.db.exists(m, n)]
        if names:
            ordered[m] = [_clean(frappe.get_doc(m, n).as_dict(no_nulls=True)) for n in names]
    ordered.update(docs)

    report = {"copied": [], "blanked": []}
    for rows in ordered.values():
        for row in rows:
            _handle_files(row, report, files_dir)

    fakes = _collect_fakes(ordered)
    name_res = [(re.compile(r"\b" + re.escape(k) + r"\b"), v) for k, v in NAME_MAP.items()]
    ordered = _apply(ordered, fakes, name_res)

    for fn in os.listdir(data_dir):
        if fn.endswith(".json"):
            os.remove(os.path.join(data_dir, fn))
    for dt, rows in ordered.items():
        with open(os.path.join(data_dir, frappe.scrub(dt) + ".json"), "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1, sort_keys=True, ensure_ascii=False, default=_json_default)
            fh.write("\n")
    with open(os.path.join(data_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({"order": list(ordered), "counts": {k: len(v) for k, v in ordered.items()}},
                  fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    print("=== EXPORTED (doctype: records) ===")
    for dt, rows in ordered.items():
        print(f"{len(rows):>5}  {dt}")
    print(f"\npersonal values replaced: {len(fakes)}")
    print(f"public files copied: {sorted(set(report['copied'])) or 'none'}")
    print(f"attachment fields blanked (private/missing/large): {sorted(set(report['blanked'])) or 'none'}")
    names_seen = sorted({r.get(k) for dt in ("Customer", "Supplier", "Tenant", "Property Owner", "RE Agent")
                         for r in ordered.get(dt, []) for k in ("customer_name", "supplier_name", "tenant_name",
                                                                 "owner_name", "agent_name") if r.get(k)})
    print(f"names kept as they are (edit NAME_MAP in tools.py if any is a real person): {names_seen}")

    text = ""
    for fn in os.listdir(data_dir):
        if fn.endswith(".json"):
            text += open(os.path.join(data_dir, fn), encoding="utf-8").read()
    leaks = [o for o in fakes if o in text]
    emails = sorted({m for m in EMAIL_RE.findall(text) if not m.lower().endswith("@example.com")})
    digits = sorted({m for m in re.findall(r"\+?\d{9,}", text) if m not in fakes.values()})[:10]
    print(f"\nLEAK CHECK: originals still present: {len(leaks)} | non-example emails: {emails or 'none'} "
          f"| long digit strings (review): {digits or 'none'}")
    print("data written to:", data_dir)


# ------------------------------------------------------------------ load

_EXISTS = {}


def _exists(doctype, name):
    key = (doctype, name)
    if key not in _EXISTS:
        _EXISTS[key] = bool(frappe.db.exists(doctype, name))
    return _EXISTS[key]


def _repair_links(rec, loading, company, stats):
    for f in frappe.get_meta(rec.doctype).get_link_fields():
        v = rec.get(f.fieldname)
        if not v or not f.options:
            continue
        if f.options == "Company":
            if not _exists("Company", v):
                rec.set(f.fieldname, company)
            continue
        if f.options in BLANK_ALWAYS or not ((f.options, v) in loading or _exists(f.options, v)):
            new = None
            if f.options in FALLBACK_FIRST and f.options not in BLANK_ALWAYS:
                new = frappe.db.get_value(f.options, FALLBACK_FIRST[f.options], "name")
            rec.set(f.fieldname, new)
            stats[f"{rec.doctype}.{f.fieldname}"] = stats.get(f"{rec.doctype}.{f.fieldname}", 0) + 1


def _ensure_agent_user(doc):
    user = doc.get("user")
    if user and not frappe.db.exists("User", user):
        frappe.get_doc({"doctype": "User", "email": user, "first_name": doc.get("agent_name") or "Agent",
                        "enabled": 0, "send_welcome_email": 0, "user_type": "System User"}
                       ).insert(ignore_permissions=True)


def _raw_insert(row, company, loading, stats):
    doc = frappe.get_doc(row)
    if doc.doctype == "RE Agent":
        _ensure_agent_user(doc)
    doc.set_parent_in_children()
    now = frappe.utils.now()
    for rec in [doc] + doc.get_all_children():
        rec.owner = rec.modified_by = "Administrator"
        rec.creation = rec.modified = now
        if rec is not doc and not rec.name:
            rec.name = frappe.generate_hash(length=10)
        _repair_links(rec, loading, company, stats)
    doc.db_insert()
    for child in doc.get_all_children():
        child.db_insert()


def _bump_series(names):
    """Advance naming counters so new documents never reuse a loaded name."""
    for name in names:
        m = re.match(r"^(.*?)(\d+)$", name)
        if m and m.group(1):
            frappe.db.sql("insert into `tabSeries` (name, `current`) values (%s, %s) "
                          "on duplicate key update `current` = greatest(`current`, %s)",
                          (m.group(1), int(m.group(2)), int(m.group(2))))


def load_data(company=None, dry_run=0):
    data_dir = _dir("data")
    with open(os.path.join(data_dir, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    company = company or frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
    if not company:
        frappe.throw("No Company on this site; create one first or pass company=...")
    plan = {}
    for dt in manifest["order"]:
        if not frappe.db.exists("DocType", dt):
            print(f"SKIP {dt}: doctype not installed on this site")
            continue
        with open(os.path.join(data_dir, frappe.scrub(dt) + ".json"), encoding="utf-8") as fh:
            plan[dt] = json.load(fh)
    loading = {(dt, r["name"]) for dt, rows in plan.items() for r in rows}
    print(f"company for records: {company}")
    if dry_run:
        for dt, rows in plan.items():
            new = sum(1 for r in rows if not frappe.db.exists(dt, r["name"]))
            print(f"{dt:26} {new:>4} new / {len(rows) - new:>4} already present")
        return

    stats, inserted, errors = {}, [], 0
    for dt, rows in plan.items():
        done = 0
        for row in rows:
            if frappe.db.exists(dt, row["name"]):
                continue
            try:
                _raw_insert(copy.deepcopy(row), company, loading, stats)
                frappe.db.commit()
                inserted.append(row["name"])
                done += 1
            except Exception as exc:
                frappe.db.rollback()
                errors += 1
                print(f"ERROR {dt} {row['name']}: {type(exc).__name__}: {str(exc)[:160]}")
        print(f"{dt:26} inserted {done}")
    _bump_series(inserted)

    files_src, files_dst = _dir("files"), frappe.get_site_path("public", "files")
    if os.path.isdir(files_src):
        os.makedirs(files_dst, exist_ok=True)
        for fn in os.listdir(files_src):
            if not os.path.exists(os.path.join(files_dst, fn)):
                shutil.copy2(os.path.join(files_src, fn), os.path.join(files_dst, fn))
    frappe.db.commit()
    frappe.clear_cache()
    print(f"\nlinks cleared (target missing / accounting): {stats or 'none'}")
    print(f"done: {len(inserted)} records inserted, {errors} errors")


@frappe.whitelist()
def run_load(dry_run=0):
    frappe.only_for("System Manager")
    return load_data(dry_run=int(dry_run))
