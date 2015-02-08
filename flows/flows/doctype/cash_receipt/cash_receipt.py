# Copyright (c) 2013, Arun Logistics and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from flows import utils
from frappe.model.document import Document

from frappe.utils import nestedset
from flows.stdlogger import root

from erpnext.accounts.general_ledger import make_gl_entries
from erpnext.stock.stock_ledger import make_sl_entries


class CashReceipt(Document):
    def __init__(self, *args, **kwargs):
        super(CashReceipt, self).__init__(*args, **kwargs)
        self.set_missing_values()

    def on_submit(self):
        self.transfer_stock()
        self.make_gl_entry()

    def on_cancel(self):
        self.transfer_stock()
        self.make_gl_entry()

    def transfer_stock(self):
        sales_person = frappe.get_doc("Sales Person", self.owner)
        stock_owner = self.owner if sales_person.is_group == 'Yes' else \
            nestedset.get_ancestors_of("Sales Person", self.owner)[0]

        stock_owner_warehouse = utils.get_or_create_warehouse(stock_owner, self.company)

        sl_entries = []

        sl_entries.append(
            self.get_sl_entry({
                "item_code": self.item,
                "actual_qty": -1 * self.qty,
                "warehouse": stock_owner_warehouse.name
            })
        )

        sl_entries.append(
            self.get_sl_entry({
                "item_code": self.item.replace('F', 'E'),
                "actual_qty": self.qty,
                "warehouse": stock_owner_warehouse.name
            })
        )

        make_sl_entries(sl_entries)


    def get_sl_entry(self, args):
        sl_dict = frappe._dict(
            {
                "posting_date": self.posting_date,
                "posting_time": self.posting_time,
                "voucher_type": self.doctype,
                "voucher_no": self.name,
                "actual_qty": 0,
                "incoming_rate": 0,
                "company": self.company,
                "fiscal_year": self.fiscal_year,
                "is_cancelled": self.docstatus == 2 and "Yes" or "No"
            })

        sl_dict.update(args)
        return sl_dict

    def get_gl_dict(self, args):
        """this method populates the common properties of a gl entry record"""
        gl_dict = frappe._dict({
            'company': self.company,
            'posting_date': self.posting_date,
            'voucher_type': self.doctype,
            'voucher_no': self.name,
            'aging_date': self.get("aging_date") or self.posting_date,
            'remarks': self.get("remarks"),
            'fiscal_year': self.fiscal_year,
            'debit': 0,
            'credit': 0,
            'is_opening': "No"
        })
        gl_dict.update(args)
        return gl_dict

    def make_gl_entry(self):

        gl_entries = []

        company_abbr = frappe.db.get_value(
            "Company", self.company, "abbr"
        )

        owners_account = utils.get_or_or_create_customer_like_gl_account(self.company, self.owner)
        sales_account = 'Sales - {}'.format(company_abbr)

        cost_center = 'Main - {}'.format(company_abbr)

        root.debug("owners account name {}".format(owners_account))

        if self.total:
            gl_entries.append(
                self.get_gl_dict({
                    "account": owners_account,
                    "debit": self.total,
                    "remarks": "Against CR {}".format(self.name),
                })
            )

            gl_entries.append(
                self.get_gl_dict({
                    "account": sales_account,
                    "credit": self.total,
                    "cost_center": cost_center,
                    "remarks": "Against CR {}".format(self.name),
                })
            )

        if gl_entries:
            make_gl_entries(
                gl_entries,
                cancel=(self.docstatus == 2),
                update_outstanding='Yes',
                merge_entries=False
            )

    def set_missing_values(self):
        from frappe.utils import today, now
        from erpnext.accounts.utils import get_fiscal_year

        for fieldname in ["posting_date", "posting_time"]:
            if not self.get(fieldname):
                self.set(fieldname, today())

        if not self.get("fiscal_year"):
            self.fiscal_year = get_fiscal_year(today())[0]

        if not self.get("posting_time"):
            self.posting_time = now()