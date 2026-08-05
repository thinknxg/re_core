frappe.ui.form.on('Property', {
    is_live: function(frm) {
        if (frm.doc.is_live) {
            frm.set_value('portal_visibility', 'Live');
            frm.set_value('published_on', frappe.datetime.now_datetime());
        } else {
            frm.set_value('portal_visibility', 'Draft');
            frm.set_value('published_on', '');
        }
    },

    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(frm.doc.is_live ? __('Unpublish') : __('Publish Live'), function() {
                frm.set_value('is_live', frm.doc.is_live ? 0 : 1);
                frm.save();
            }).addClass(frm.doc.is_live ? 'btn-danger' : 'btn-primary');

            frm.add_custom_button(__('New Lease Contract'), function() {
                frappe.new_doc('Lease Contract', {
                    property: frm.doc.name,
                    company: frm.doc.company,
                });
            }, __('Create'));

            frappe.db.count('Lease Contract', { filters: { property: frm.doc.name } }).then((count) => {
                if (count > 0) {
                    frm.add_custom_button(__('Lease Contracts ({0})', [count]), function() {
                        frappe.set_route('list', 'Lease Contract', { property: frm.doc.name });
                    }, __('View'));
                }
            });
        }
    }
});
