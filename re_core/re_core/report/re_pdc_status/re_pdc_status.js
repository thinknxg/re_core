frappe.query_reports["RE PDC Status"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "tenant", label: __("Tenant"), fieldtype: "Link", options: "Tenant" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nReceived\nDeposited\nCleared\nBounced\nReplaced\nReturned",
		},
		{ fieldname: "from_date", label: __("Cheque Date From"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("Cheque Date To"), fieldtype: "Date" },
	],
};
