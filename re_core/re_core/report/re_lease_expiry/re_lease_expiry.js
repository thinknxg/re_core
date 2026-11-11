frappe.query_reports["RE Lease Expiry"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property" },
		{ fieldname: "tenant", label: __("Tenant"), fieldtype: "Link", options: "Tenant" },
		{ fieldname: "days_ahead", label: __("Expiring Within (days)"), fieldtype: "Int", default: 90 },
	],
};
