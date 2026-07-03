frappe.ui.form.on("Lease Contract", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && ["Active", "Expiring"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Terminate Lease"), () => {
				frappe.prompt(
					[
						{ fieldname: "termination_date", fieldtype: "Date", label: __("Termination Date"),
						  default: frappe.datetime.get_today(), reqd: 1 },
						{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason") },
					],
					(values) => {
						frm.call("terminate", values).then(() => frm.reload_doc());
					},
					__("Terminate Lease"), __("Terminate")
				);
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
});
