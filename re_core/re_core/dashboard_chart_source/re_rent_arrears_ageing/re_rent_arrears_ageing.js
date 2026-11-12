frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["RE Rent Arrears Ageing"] = {
	method: "re_core.re_core.dashboard_chart_source.re_rent_arrears_ageing.re_rent_arrears_ageing.get",
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
	],
};
