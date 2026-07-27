frappe.ui.form.on("Property", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Add Unit"), () => {
                frappe.new_doc("Unit", {
                    property: frm.doc.name,
                });
            });
        }
    },
});
