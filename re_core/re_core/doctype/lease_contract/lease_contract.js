frappe.ui.form.on("Lease Contract", {
refresh(frm) {
if (frm.doc.docstatus === 1 && ["Active", "Expiring"].includes(frm.doc.status)) {
frm.add_custom_button(__("Terminate Lease"), () => {
const dialog = new frappe.ui.Dialog({
title: __("Terminate Lease"),
fields: [
{ fieldname: "termination_date", fieldtype: "Date", label: __("Schedule End Date"),
  default: frappe.datetime.get_today(), reqd: 1 },
{ fieldname: "reasons", fieldtype: "Select", label: __("Reasons"),
  options: ["New Contract", "Lost to another agent", "Tenancy Surrendered",
            "End of Tenancy", "Tenancy Breach", "Break Clause Activation"],
  default: "New Contract", reqd: 1 },
{ fieldname: "security_deposit_amount", fieldtype: "Currency",
  label: __("Security Deposit"), default: frm.doc.security_deposit_amount, read_only: 1 },
{ fieldname: "apply_charge_to_tenant", fieldtype: "Check",
  label: __("Apply Charge to Tenant") },
{ fieldname: "rent_sb", fieldtype: "Section Break", label: __("Rent") },
{ fieldname: "outstanding_rent", fieldtype: "Currency", label: __("Outstanding Rent") },
{ fieldname: "calculate_amount", fieldtype: "Button", label: __("Calculate Amount"),
  click: () => {
const upto = dialog.get_value("termination_date");
frm.call("get_outstanding_rent", { upto_date: upto }).then(r => {
dialog.set_value("outstanding_rent", r.message || 0);
});
  } },
{ fieldname: "col_break_term", fieldtype: "Column Break" },
{ fieldname: "mode_of_payment", fieldtype: "Link", label: __("Mode of Payment"),
  options: "Mode of Payment" },
{ fieldname: "reason", fieldtype: "Small Text", label: __("Notes") },
],
primary_action_label: __("Terminate"),
primary_action: (values) => {
frm.call("terminate", values).then(() => {
dialog.hide();
frm.reload_doc();
if (values.reasons === "New Contract") {
frappe.new_doc("Lease Contract", {
tenant: frm.doc.tenant,
unit: frm.doc.unit,
property: frm.doc.property,
});
}
});
},
});
dialog.show();
}).addClass("btn-danger");
}
if (frm.doc.rent_schedule) {
frm.add_custom_button(__("Rent Schedule"), () =>
frappe.set_route("Form", "Rent Schedule", frm.doc.rent_schedule), __("View"));
}
if (frm.doc.security_deposit) {
frm.add_custom_button(__("Security Deposit"), () =>
frappe.set_route("Form", "Security Deposit", frm.doc.security_deposit), __("View"));
}
},
unit(frm) { auto_populate_lease_charges(frm, false); },
property(frm) { auto_populate_lease_charges(frm, false); },
start_date(frm) { auto_populate_lease_charges(frm, false); },
end_date(frm) { auto_populate_lease_charges(frm, false); },
});

function auto_populate_lease_charges(frm, force) {
if (frm.doc.docstatus !== 0) return;
if (!frm.doc.property && !frm.doc.unit) return;
if (!frm.doc.start_date || !frm.doc.end_date) return;
// Don't clobber manually entered/edited rows unless the admin explicitly
// clicked "Auto-fill Charges" (force = true). A freshly opened form can
// have a single blank grid row by default - that doesn't count as
// "already has data".
const has_real_charge_rows = (frm.doc.charges || []).some(r => r.amount);
if (!force && has_real_charge_rows) return;

frappe.call({
method: "re_core.re_core.api.get_lease_term_charges_preview",
args: {
property: frm.doc.property,
unit: frm.doc.unit,
start_date: frm.doc.start_date,
end_date: frm.doc.end_date,
},
callback: (r) => {
const charges = (r.message && r.message.charges) || [];
if (!charges.length) return;
frm.clear_table("charges");
charges.forEach((c) => {
const row = frm.add_child("charges");
row.charge_type = c.charge_type;
row.description = c.description;
row.amount = c.amount;
});
frm.refresh_field("charges");
frappe.show_alert({
message: __("Charges auto-filled from Property/Unit ({0} rows). Review and edit as needed.", [charges.length]),
indicator: "green",
});
},
});
}
