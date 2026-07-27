// Copyright (c) 2026, Kreatao and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tenancy Bulk Payment", {
refresh(frm) {
if (frm.doc.docstatus === 0) {
frm.add_custom_button(__("Fetch Due Installments"), () => {
if (!frm.doc.property || !frm.doc.from_date || !frm.doc.to_date) {
frappe.msgprint(__("Please set Property, From Date and To Date first."));
return;
}
if (frm.is_dirty()) {
frappe.msgprint(__("Please save the document before fetching installments."));
return;
}
frappe.dom.freeze(__("Fetching due installments..."));
frm.call("fetch_due_installments")
.then((r) => {
frappe.dom.unfreeze();
frm.reload_doc();
frappe.show_alert({
message: __("{0} installment(s) fetched.", [r.message]),
indicator: "green",
});
})
.catch(() => frappe.dom.unfreeze());
}).addClass("btn-primary");
}

if (frm.doc.docstatus === 1) {
frm.dashboard.add_indicator(
__("Status: {0}", [frm.doc.status]),
frm.doc.status === "Processed" ? "green" : "orange"
);
}
},

property(frm) {
frm.set_value("rows", []);
},

from_date(frm) {
frm.set_value("rows", []);
},

to_date(frm) {
frm.set_value("rows", []);
},
});

frappe.ui.form.on("Tenancy Bulk Payment Row", {
pay_amount(frm, cdt, cdn) {
const row = locals[cdt][cdn];
if (flt(row.pay_amount) > flt(row.outstanding_amount)) {
frappe.msgprint(__("Pay Amount cannot exceed Outstanding Amount for row {0}.", [row.idx]));
frappe.model.set_value(cdt, cdn, "pay_amount", row.outstanding_amount);
}
},

cheque_no(frm, cdt, cdn) {
const row = locals[cdt][cdn];
if (row.cheque_no && !row.cheque_date) {
frappe.model.set_value(cdt, cdn, "cheque_date", frappe.datetime.get_today());
}
},
});
