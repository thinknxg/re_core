frappe.query_reports["RE Maintenance Overview"] = {
	filters: [
		{ fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property" },
		{
			fieldname: "category",
			label: __("Category"),
			fieldtype: "Select",
			options: "\nPlumbing\nElectrical\nAC\nCivil\nAppliances\nPest Control\nOther",
		},
		{ fieldname: "priority", label: __("Priority"), fieldtype: "Select", options: "\nLow\nMedium\nHigh\nEmergency" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nOpen\nIn Progress\nOn Hold\nCompleted\nRejected\nCancelled",
		},
		{ fieldname: "open_only", label: __("Open Requests Only"), fieldtype: "Check", default: 1 },
	],
};
