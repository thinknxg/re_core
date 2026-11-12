frappe.query_reports["RE Outstanding Rent"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "tenant", label: __("Tenant"), fieldtype: "Link", options: "Tenant" },
		{ fieldname: "from_date", label: __("Due From"), fieldtype: "Date" },
		{ fieldname: "as_on_date", label: __("As On Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
	],
};
