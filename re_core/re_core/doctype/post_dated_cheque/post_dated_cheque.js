frappe.ui.form.on("Post Dated Cheque", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		const move = (method, args = {}) => frm.call(method, args).then(() => frm.reload_doc());

		if (frm.doc.status === "Received") {
			frm.add_custom_button(__("Mark Deposited"), () => move("mark_deposited"))
				.addClass("btn-primary");
		}
		if (frm.doc.status === "Deposited") {
			frm.add_custom_button(__("Mark Cleared"), () => move("mark_cleared"))
				.addClass("btn-success");
			frm.add_custom_button(__("Mark Bounced"), () => {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("Bounce Reason") }],
					(v) => move("mark_bounced", v), __("Mark Bounced"), __("Confirm"));
			}).addClass("btn-danger");
		}
	},
});
