# Copyright (c) 2026, Kreatao and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

from re_core.re_core.api import record_partial_payment


class TenancyBulkPayment(Document):
    @frappe.whitelist()
    def fetch_due_installments(self):
        if not (self.property and self.from_date and self.to_date):
            frappe.throw(_("Property, From Date and To Date are required before fetching installments."))

        self.set("rows", [])
        for r in self.get_due_installments():
            self.append("rows", {
                "rent_installment": r.rent_installment,
                "lease_contract": r.lease_contract,
                "tenant": r.tenant,
                "due_date": r.due_date,
                "amount": r.amount,
                "outstanding_amount": r.outstanding_amount,
                "pay_amount": r.outstanding_amount,
                "mode_of_payment": self.mode_of_payment or "Cash",
                "status": "Pending",
            })
        self.save()
        return len(self.rows)

    def get_due_installments(self):
        return frappe.db.sql("""
            select
                ri.name as rent_installment,
                ri.due_date,
                ri.amount,
                ri.outstanding_amount,
                ri.sales_invoice,
                rs.name as rent_schedule,
                rs.lease_contract,
                rs.tenant
            from `tabRent Installment` ri
            inner join `tabRent Schedule` rs on rs.name = ri.parent
            inner join `tabLease Contract` lc on lc.name = rs.lease_contract
            where lc.property = %(property)s
            and ri.due_date between %(from_date)s and %(to_date)s
            and ri.status in ('Pending', 'Partially Paid')
            and ifnull(ri.sales_invoice, '') != ''
            order by ri.due_date
        """, {
            "property": self.property,
            "from_date": self.from_date,
            "to_date": self.to_date,
        }, as_dict=True)

    def on_submit(self):
        if not self.rows:
            frappe.throw(_("No rows to process. Fetch due installments first."))

        failures = 0
        processed = 0

        for row in self.rows:
            if row.status == "Paid":
                processed += 1
                continue

            pay_amount = flt(row.pay_amount)
            if pay_amount <= 0:
                row.db_set("status", "Failed")
                failures += 1
                continue

            savepoint = f"tbp_row_{row.name}"
            frappe.db.savepoint(savepoint)
            try:
                result = record_partial_payment(
                    installment_name=row.rent_installment,
                    amount=pay_amount,
                    mode_of_payment=row.mode_of_payment or self.mode_of_payment or "Cash",
                    payment_date=nowdate(),
                    remarks=_("Bulk PDC entry {0}, cheque {1}").format(self.name, row.cheque_no or ""),
                )
                payment_entry = None
                if result.get("installments_paid"):
                    payment_entry = result["installments_paid"][0]["payment_entry"]

                pdc_name = None
                if row.cheque_no:
                    pdc_doc = frappe.get_doc({
                        "doctype": "Post Dated Cheque",
                        "tenant": row.tenant,
                        "lease_contract": row.lease_contract,
                        "company": self.company,
                        "cheque_no": row.cheque_no,
                        "bank": row.bank,
                        "bank_account": row.bank_account,
                        "cheque_date": row.cheque_date,
                        "amount": pay_amount,
                        "status": "Cleared",
                        "deposit_date": nowdate(),
                        "clearance_date": nowdate(),
                        "payment_entry": payment_entry,
                    })
                    pdc_doc.insert(ignore_permissions=True)
                    pdc_name = pdc_doc.name
                    frappe.db.set_value("Rent Installment", row.rent_installment, "pdc", pdc_name)

                row.db_set("payment_entry", payment_entry)
                row.db_set("pdc", pdc_name)
                row.db_set("status", "Paid")
                processed += 1
            except Exception:
                frappe.db.rollback(save_point=savepoint)
                row.db_set("status", "Failed")
                failures += 1
                frappe.log_error(
                    title=f"Tenancy Bulk Payment {self.name} row failed",
                    message=frappe.get_traceback(),
                )

        self.db_set("status", "Processed" if failures == 0 else "Partially Processed")

        if failures:
            frappe.msgprint(
                _("{0} of {1} installments failed to process. Check Error Log for details.")
                .format(failures, len(self.rows)),
                indicator="orange",
            )
