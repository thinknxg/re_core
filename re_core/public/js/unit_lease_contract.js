frappe.ui.form.on('Unit', {
    refresh: function(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__('New Lease Contract'), function() {
            frappe.new_doc('Lease Contract', {
                property: frm.doc.property,
                unit: frm.doc.name,
                company: frm.doc.company,
            });
        }, __('Create'));

        frappe.db.count('Lease Contract', { filters: { unit: frm.doc.name } }).then((count) => {
            if (count > 0) {
                frm.add_custom_button(__('Lease Contracts ({0})', [count]), function() {
                    frappe.set_route('list', 'Lease Contract', { unit: frm.doc.name });
                }, __('View'));
            }
        });
    }
});
