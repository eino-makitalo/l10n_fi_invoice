# -*- coding: utf-8 -*-
from openerp import models, fields, api
# noinspection PyProtectedMember
from openerp.tools.translate import _
import re
import logging

from openerp.exceptions import UserError

class AccountBankStatementWithFinnishRefnumber(models.Model):
    _inherit = "account.bank.statement"
    @api.multi
    def reconciliation_widget_preprocess(self):   
        return super(AccountBankStatementWithFinnishRefnumber, self).reconciliation_widget_preprocess()    
 
class AccountBankStatementLineFinnishRefNumber(models.Model):
    """account.invoice .... refnumber -- statement reference  reconile=False
    laskusta -> move_id -> account_move -> move_id -> account_move_line jossa reconcile=FALSE
    
    1) etsi avoin lasku jossa sama viitenumero kuin statement rivillä
    2) siirry account_move riveihin...
    3) valitse vain receivable/payable tilit
    4) jos näitä rivejä on vain yksi valitse se...
    """ 
    _inherit = "account.bank.statement.line"
    @api.multi
    def auto_reconcile(self):
        """ Very Ugly way but in Finland we use just reference numbers to match payments... so we try this approach first
            Try to automatically reconcile the statement.line ; return the counterpart journal entry/ies if the automatic reconciliation succeeded, False otherwise.
            TODO : this method could be greatly improved and made extensible
        """
        done=False
        self.ensure_one()
        refnum = self.ref.replace(' ','')
        match_invoices = self.env['account.invoice']
        #invoice_found=match_invoices.search([('ref_number', '=', refnum), ('reconciled', '=', False)], limit=2)
        invoice_found=match_invoices.search([('ref_number', '=', refnum) ], limit=2)
        if len(invoice_found)!=1:
            return super(AccountBankStatementLineFinnishRefNumber,self).auto_reconcile()

        match_recs = self.env['account.move.line']

        # Check move id where referene is
        move_id=invoice_found.move_id.id

        # Time to fetch right line
        
        
        # Look just these IDS
        domain = [('move_id', '=', move_id)]
        match_recs = self.get_move_lines_for_reconciliation(limit=2, additional_domain=domain, overlook_partner=True)


        if not match_recs:
            return super(AccountBankStatementLineFinnishRefNumber,self).auto_reconcile()

        # Now reconcile
        counterpart_aml_dicts = []
        payment_aml_rec = self.env['account.move.line']
        for aml in match_recs:
            if aml.account_id.internal_type == 'liquidity':
                payment_aml_rec = (payment_aml_rec | aml)
            else:
                amount = aml.currency_id and aml.amount_residual_currency or aml.amount_residual
                counterpart_aml_dicts.append({
                    'name': aml.name if aml.name != '/' else aml.move_id.name,
                    'debit': amount < 0 and -amount or 0,
                    'credit': amount > 0 and amount or 0,
                    'move_line': aml
                })

        try:
            with self._cr.savepoint():
                counterpart = self.process_reconciliation(counterpart_aml_dicts=counterpart_aml_dicts, payment_aml_rec=payment_aml_rec)
            return counterpart
        except UserError:
            # A configuration / business logic error that makes it impossible to auto-reconcile should not be raised
            # since automatic reconciliation is just an amenity and the user will get the same exception when manually
            # reconciling. Other types of exception are (hopefully) programmation errors and should cause a stacktrace.
            self.invalidate_cache()
            self.env['account.move'].invalidate_cache()
            self.env['account.move.line'].invalidate_cache()
            return False
