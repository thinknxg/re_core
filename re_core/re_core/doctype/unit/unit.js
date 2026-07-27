frappe.ui.form.on("Unit", {
    property(frm) {
        if (frm.doc.property) {
            frappe.db.get_value("Property", frm.doc.property, ["ownership_type", "owner_ref"])
                .then(({ message }) => {
                    frm.set_value("ownership_type", message.ownership_type);
                    frm.set_value("owner_ref", message.owner_ref);
                });
        } else {
            frm.set_value("ownership_type", "");
            frm.set_value("owner_ref", "");
        }
    },
});
