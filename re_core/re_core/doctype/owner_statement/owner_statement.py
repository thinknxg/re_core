import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from re_core.re_core.owner_remittance import _get_or_create_remittance_item


class OwnerStatement(Document):
	def on_submit(self):
		self.create_remittance_purchase_invoice()

	def create_remittance_purchase_invoice(self):
		if self.purchase_invoice:
			return  # already generated, don't duplicate

		if flt(self.net_payable) <= 0:
			frappe.log_error(
				title="Owner Statement - Non-positive net amount",
				message=(
					f"Owner Statement {self.name} has net_payable {self.net_payable}. "
					f"Skipping Purchase Invoice creation."
				),
			)
			return

		supplier = frappe.db.get_value("Property Owner", self.property_owner, "supplier")
		if not supplier:
			frappe.log_error(
				title="Owner Statement - No Supplier",
				message=f"Property Owner {self.property_owner} has no linked Supplier. Statement: {self.name}",
			)
			return

		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"supplier": supplier,
			"company": self.company,
			"custom_owner_statement": self.name,
			"items": [{
				"item_code": _get_or_create_remittance_item(),
				"qty": 1,
				"rate": self.net_payable,
				"description": (
					f"Owner remittance for {self.name} ({self.period_from} to {self.period_to}) - "
					f"rent {self.rent_invoiced}, less management fee {self.management_fee}"
					+ (f", less onetime commission {self.onetime_commission_deducted}"
					   if self.onetime_commission_deducted else "")
					+ (f", less owner expenses {self.owner_expenses}" if self.owner_expenses else "")
				),
			}],
		})
		pi.insert(ignore_permissions=True)

		self.db_set("purchase_invoice", pi.name)

		frappe.msgprint(
			_("Owner remittance Purchase Invoice {0} created for {1}").format(pi.name, supplier),
			alert=True,
		)
