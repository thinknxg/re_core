frappe.ui.form.on('Unit', {
    property: function(frm) {
        if (!frm.doc.property) return;

        frappe.db.get_doc('Property', frm.doc.property).then(prop => {
            // Always sync read-only reference fields
            frm.set_value('ownership_type', prop.ownership_type);
            frm.set_value('owner_ref', prop.owner_ref);

            // Only default the editable override fields if this Unit doesn't
            // already have its own values - never clobber a manual override
            if (!frm.doc.management_fee_type) {
                frm.set_value('management_fee_type', prop.management_fee_type);
            }
            if (!frm.doc.management_fee_value) {
                frm.set_value('management_fee_value', prop.management_fee_value);
            }
            if (!frm.doc.onetime_commission) {
                frm.set_value('onetime_commission', prop.onetime_commission);
            }
        });
    }
});
