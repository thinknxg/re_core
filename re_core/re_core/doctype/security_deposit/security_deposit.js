frappe.ui.form.on("Security Deposit", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Held") {
			frm.add_custom_button(__("Refund / Settle"), () => {
				frappe.prompt(
					[
						{ fieldname: "deduction_amount", fieldtype: "Currency",
						  label: __("Deduction Amount"), default: frm.doc.deduction_amount || 0 },
						{ fieldname: "deduction_reason", fieldtype: "Small Text",
						  label: __("Deduction Reason"), default: frm.doc.deduction_reason },
					],
					(v) => frm.call("refund", v).then(() => frm.reload_doc()),
					__("Settle Deposit"), __("Process")
				);
			}).addClass("btn-primary");
		}
	},
});
