import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, date_diff, flt, getdate, month_diff

FREQUENCY_COUNT = {"Annual": 1, "Semi-Annual": 2, "Quarterly": 4}


class LeaseContract(Document):
    # ------------------------------------------------------------ validate
    def validate(self):
        self._set_company()
        self._validate_dates()
        self._validate_unit()
        self._compute_totals()
        self.title = f"{self.tenant_name or self.tenant} @ {self.unit}"

    def _set_company(self):
        if not self.company and self.property:
            self.company = frappe.db.get_value("Property", self.property, "company")

    def _validate_dates(self):
        if getdate(self.end_date) <= getdate(self.start_date):
            frappe.throw(_("End Date must be after Start Date."))
        self.duration_months = month_diff(self.end_date, self.start_date)

    def _validate_unit(self):
        status, current = frappe.db.get_value("Unit", self.unit, ["status", "current_lease"])
        if self.docstatus == 0 and status not in ("Vacant", "Reserved") and current != self.name:
            frappe.throw(_("Unit {0} is {1}. Only Vacant or Reserved units can be leased.")
                         .format(self.unit, status))
        self._validate_no_duplicate_draft()

    def _validate_no_duplicate_draft(self):
        """Prevent two visitors/agents from independently creating a second
        pending Draft Lease Contract for the same unit while one is already
        awaiting approval - closes the double-booking race condition.
        """
        if self.docstatus != 0:
            return
        other_draft = frappe.db.get_value(
            "Lease Contract",
            {"unit": self.unit, "docstatus": 0, "name": ["!=", self.name or ""]},
            "name",
        )
        if other_draft:
            frappe.throw(_(
                "Unit {0} already has a pending lease request ({1}). "
                "Please wait for it to be approved or rejected before submitting another."
            ).format(self.unit, other_draft))

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

    def _flag_security_deposit(self, reason):
        if not self.security_deposit:
            return
        status = frappe.db.get_value("Security Deposit", self.security_deposit, "status")
        if status != "Held":
            return
        deposit = frappe.get_doc("Security Deposit", self.security_deposit)
        deposit.add_comment(
            "Comment",
            _("Lease {0} {1} — deposit needs refund/deduction review.").format(self.name, reason)
        )
        for user in frappe.get_all("Has Role",
                                   filters={"role": "RE Manager", "parenttype": "User"},
                                   pluck="parent"):
            if frappe.db.get_value("User", user, "enabled"):
                frappe.get_doc({
                    "doctype": "Notification Log",
                    "for_user": user,
                    "type": "Alert",
                    "document_type": "Security Deposit",
                    "document_name": self.security_deposit,
                    "subject": _("Security Deposit {0} needs review — lease {1} {2}")
                               .format(self.security_deposit, self.name, reason),
                }).insert(ignore_permissions=True)

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
        self._flag_security_deposit(_("was cancelled"))
        if self.rent_schedule:
            frappe.db.set_value("Rent Schedule", self.rent_schedule, "status", "Cancelled")
            for row in frappe.get_all("Rent Installment",
                                      filters={"parent": self.rent_schedule,
                                               "status": ["in", ["Pending", "Overdue"]]},
                                      pluck="name"):
                frappe.db.set_value("Rent Installment", row, "status", "Cancelled")

    # ------------------------------------------------------------ actions
    @frappe.whitelist()
    def terminate(self, termination_date=None, reason=None, reasons=None,
                  outstanding_rent=None, mode_of_payment=None, apply_charge_to_tenant=None):
        """Early termination without cancelling the submitted document.

        reasons: one of New Contract / Lost to another agent / Tenancy Surrendered /
                 End of Tenancy / Tenancy Breach / Break Clause Activation.
                 "New Contract" holds the unit as Reserved (a new lease is coming);
                 every other reason frees it to Vacant, same as before.
        """
        if self.docstatus != 1 or self.status not in ("Active", "Expiring"):
            frappe.throw(_("Only Active or Expiring leases can be terminated."))
        expected_rent = self.get_outstanding_rent(upto_date=termination_date)
        if flt(outstanding_rent, 3) != flt(expected_rent, 3):
            frappe.throw(_(
                "Outstanding Rent {0} does not match the calculated amount {1} for this lease. "
                "Use Calculate Amount to fetch the correct figure before terminating."
            ).format(flt(outstanding_rent, 3), flt(expected_rent, 3)))
        self.db_set("status", "Terminated")
        unit_status = "Reserved" if reasons == "New Contract" else "Vacant"
        frappe.db.set_value("Unit", self.unit, {"status": unit_status, "current_lease": None})
        self._flag_security_deposit(_("was terminated early"))
        note_parts = []
        if reason:
            note_parts.append(reason)
        if reasons:
            note_parts.append(_("Reason: {0}").format(reasons))
        if flt(outstanding_rent):
            note_parts.append(_("Outstanding Rent: {0}").format(outstanding_rent))
        if mode_of_payment:
            note_parts.append(_("Mode of Payment: {0}").format(mode_of_payment))
        if apply_charge_to_tenant:
            note_parts.append(_("Charge applied to tenant"))
        if note_parts:
            self.add_comment("Comment", _("Terminated: {0}").format(" | ".join(note_parts)))
        for row in frappe.get_all("Rent Installment",
                                  filters={"parent": self.rent_schedule,
                                           "status": ["in", ["Pending", "Overdue"]],
                                           "due_date": [">", termination_date or frappe.utils.today()]},
                                  pluck="name"):
            frappe.db.set_value("Rent Installment", row, "status", "Cancelled")
        return self.status

    @frappe.whitelist()
    def get_outstanding_rent(self, upto_date=None):
        """Sum unpaid Rent Installments due on/before upto_date (Calculate Amount button)."""
        if not self.rent_schedule:
            return 0
        filters = {"parent": self.rent_schedule, "status": ["in", ["Pending", "Overdue"]]}
        if upto_date:
            filters["due_date"] = ["<=", upto_date]
        rows = frappe.get_all("Rent Installment", filters=filters, pluck="amount")
        return flt(sum(flt(a) for a in rows), 3)
