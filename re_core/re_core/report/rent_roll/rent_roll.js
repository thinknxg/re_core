frappe.query_reports["Rent Roll"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property" },
		{ fieldname: "status", label: __("Unit Status"), fieldtype: "Select",
		  options: "\nVacant\nReserved\nOccupied\nUnder Maintenance\nBlocked" },
	],
};
