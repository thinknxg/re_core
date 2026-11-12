import frappe

from re_core.re_core.ops_dashboard import billed_vs_collected_chart


@frappe.whitelist()
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	filters = frappe.parse_json(filters) or {}
	if chart_name and not filters:
		filters = frappe.parse_json(frappe.db.get_value("Dashboard Chart", chart_name, "filters_json")) or {}
	if isinstance(filters, list):
		filters = {}
	return billed_vs_collected_chart(company=filters.get("company"))
