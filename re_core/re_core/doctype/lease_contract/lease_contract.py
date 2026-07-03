import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, date_diff, flt, getdate, month_diff

FREQUENCY_COUNT = {"Annual": 1, "Semi-Annual": 2, "Quarterly": 4}


class LeaseContract(Document):
    # ------------------------------------------------------------ validate
    def validate(self):
        self._validate_dates()
        self._validate_unit()
        self._compute_totals()
        self.title = f"{self.tenant_name or self.tenant} @ {self.unit}"

    def _validate_dates(self):
        if getdate(self.end_date) <= getdate(self.start_date):
            frappe.throw(_("End Date must be after Start Date."))
        self.duration_months = month_diff(self.end_date, self.start_date)

    def _validate_unit(self):
        status, current = frappe.db.get_value("Unit", self.unit, ["status", "current_lease"])
        if self.docstatus == 0 and status not in ("Vacant", "Reserved") and current != self.name:
            frappe.throw(_("Unit {0} is {1}. Only Vacant or Reserved units can be leased.")
                         .format(self.unit, status))

    def _compute_totals(self):
        if not self.charges:
            frappe.throw(_("Add at least one Lease Charge row."))
        self.total_contract_value = sum(flt(c.amount) for c in self.charges)

    # ------------------------------------------------------------ submit
    def on_submit(self):
        self.db_set("status", "Active")
        frappe.db.set_value("Unit", self.unit,
                            {"status": "Occupied", "current_lease": self.name})
        schedule = self._create_rent_schedule()
        self.db_set("rent_schedule", schedule.name)
        if flt(self.security_deposit_amount) > 0:
            deposit = self._create_security_deposit()
            self.db_set("security_deposit", deposit.name)
        if frappe.db.get_single_value("Property Settings", "auto_create_pdcs"):
            self._draft_pdcs(schedule)

    def _installment_count(self):
        if self.payment_frequency == "Custom":
            if not self.custom_installments or self.custom_installments < 1:
                frappe.throw(_("Set the Number of Cheques for a Custom frequency."))
            return int(self.custom_installments)
        if self.payment_frequency == "Monthly":
            return max(int(self.duration_months or 1), 1)
        return FREQUENCY_COUNT.get(self.payment_frequency, 1)

    def _create_rent_schedule(self):
        count = self._installment_count()
        total = flt(self.total_contract_value)
        per = flt(total / count, 3)  # OMR: 3 decimal places
        step_months = max((self.duration_months or count) // count, 1)

        schedule = frappe.new_doc("Rent Schedule")
        schedule.lease_contract = self.name
        schedule.total_amount = total
        running = 0.0
        for i in range(count):
            amount = per if i < count - 1 else flt(total - running, 3)
            running += per
            schedule.append("installments", {
                "installment_no": i + 1,
                "due_date": add_months(getdate(self.start_date), i * step_months),
                "amount": amount,
                "status": "Pending",
            })
        schedule.insert(ignore_permissions=True)
        return schedule

    def _create_security_deposit(self):
        deposit = frappe.new_doc("Security Deposit")
        deposit.tenant = self.tenant
        deposit.lease_contract = self.name
        deposit.amount = self.security_deposit_amount
        deposit.received_date = self.start_date
        deposit.insert(ignore_permissions=True)
        return deposit

    def _draft_pdcs(self, schedule):
        for row in schedule.installments:
            pdc = frappe.new_doc("Post Dated Cheque")
            pdc.tenant = self.tenant
            pdc.lease_contract = self.name
            pdc.cheque_no = f"TBC-{self.name}-{row.installment_no}"
            pdc.bank = "TBC"
            pdc.cheque_date = row.due_date
            pdc.amount = row.amount
            pdc.insert(ignore_permissions=True)
            frappe.db.set_value("Rent Installment", row.name, "pdc", pdc.name)

    # ------------------------------------------------------------ cancel
    def on_cancel(self):
        self.db_set("status", "Terminated")
        frappe.db.set_value("Unit", self.unit, {"status": "Vacant", "current_lease": None})
        if self.rent_schedule:
            frappe.db.set_value("Rent Schedule", self.rent_schedule, "status", "Cancelled")
            for row in frappe.get_all("Rent Installment",
                                      filters={"parent": self.rent_schedule,
                                               "status": ["in", ["Pending", "Overdue"]]},
                                      pluck="name"):
                frappe.db.set_value("Rent Installment", row, "status", "Cancelled")

    # ------------------------------------------------------------ actions
    @frappe.whitelist()
    def terminate(self, termination_date=None, reason=None):
        """Early termination without cancelling the submitted document."""
        if self.docstatus != 1 or self.status not in ("Active", "Expiring"):
            frappe.throw(_("Only Active or Expiring leases can be terminated."))
        self.db_set("status", "Terminated")
        frappe.db.set_value("Unit", self.unit, {"status": "Vacant", "current_lease": None})
        if reason:
            self.add_comment("Comment", _("Terminated: {0}").format(reason))
        for row in frappe.get_all("Rent Installment",
                                  filters={"parent": self.rent_schedule,
                                           "status": ["in", ["Pending", "Overdue"]],
                                           "due_date": [">", termination_date or frappe.utils.today()]},
                                  pluck="name"):
            frappe.db.set_value("Rent Installment", row, "status", "Cancelled")
        return self.status
