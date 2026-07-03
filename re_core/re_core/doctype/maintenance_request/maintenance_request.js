frappe.ui.form.on("Maintenance Request", {
	refresh(frm) {
		if (!frm.is_new() && !frm.doc.maintenance_job &&
			["Open", "On Hold"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Create Job"), () =>
				frm.call("make_job").then((r) =>
					frappe.set_route("Form", "Maintenance Job", r.message))
			).addClass("btn-primary");
		}
	},
});
