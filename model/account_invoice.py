# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Avoin.Systems
#    Copyright 2015 Avoin.Systems
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api
# noinspection PyProtectedMember
from openerp.tools.translate import _
import re
import logging
from openerp.exceptions import Warning,UserError, ValidationError

from checkref import calc_checksum


log = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def _formatref(callback,val01):
        if val01:
            val01=val01.replace(u' ','')            
            if len(val01)>5:
                palat=[val01[i:i+5] for i in range(0, len(val01), 5)]
                return " ".join(palat)  # Recommended format for ref number 
        return val01
    
    

    @api.constrains('ref_number')
    def _checkref(self):
        errmsg=None
        try:
            for record in self:
                if record.ref_number==False:
                    return
                if len(record.ref_number.strip())>0:
                    # only numbers and spaces expected
                    val01=self.ref_number.strip()
                    val01=val01.replace(u' ','')
                    if len(val01)<2:
                        errmsg=_("Too short ref number. Smallest possible is 13 (last digit is checksum)")
                    if val01.isdigit():
                        if len(val01)>20:
                            errmsg=_("Ref number can be max 20 digits")
                            return
                        numberpart=val01[:-1]
                        checksum=val01[-1:]
                        checksum_ok = calc_checksum(numberpart)
                        if int(checksum)!=checksum_ok:
                            errmsg=_("Ref number is invalid last digit (checksum) is %d but it should be %d"%(int(checksum),checksum_ok))
                            return 
                    else:
                        errmsg= _("Ref number must be only digits and spaces")
                        return
        finally:
            if errmsg: 
                raise ValidationError(errmsg)

    @api.depends('partner_bank_id', 'company_id', 'amount_total', 'ref_number')
    def _compute_barcode_string(self):        
        primary_bank_account = self.partner_bank_id or \
            self.company_id.partner_id.bank_ids and self.company_id.partner_id.bank_ids[0]
        if (self.amount_total and primary_bank_account.acc_number
                and self.ref_number and self.date_due):
            amount_total_string = str(self.amount_total)
            if amount_total_string[-2:-1] == '.':
                amount_total_string += '0'
            amount_total_string = amount_total_string.zfill(9)
            receiver_bank_account = re\
                .sub("[^0-9]", "", str(primary_bank_account.acc_number))
            rn=self.ref_number.replace(' ','')
            ref_number_filled = rn.zfill(20)
            self.barcode_string = '4' \
                                  + receiver_bank_account \
                                  + amount_total_string[:-3] \
                                  + amount_total_string[-2:] \
                                  + "000" + ref_number_filled \
                                  + self.date_due[2:4] \
                                  + self.date_due[5:-3] \
                                  + self.date_due[-2:]
            
        else:
            self.barcode_string = False

    @api.depends('ref_number')
    def _clean_refnum(self):
        for record in self:
            record.ref_number_clean=record.ref_number.replace(' ','')
            
    ref_number = fields.Char(
        'Reference Number',
        store=True,
        translate=_formatref,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help=_('Invoice reference number in accordance with https://'
               'www.fkl.fi/teemasivut/sepa/tekninen_dokumentaatio/Do'
               'kumentit/kotimaisen_viitteen_rakenneohje.pdf')
    )
    
    ref_number_clean = fields.Char(
        'Reference Number without any space',
        store=True,
        compute='_clean_refnum'
    )

    date_delivered = fields.Date(
        'Date delivered',
        help=_('The date when the invoiced product or service was considered '
               'delivered, for taxation purposes.')
    )
    
    
    barcode_string = fields.Char(
	'Barcode String',
        compute='_compute_barcode_string',
        help=_('https://www.fkl.fi/teemasivut/sepa/tekninen_dokumentaatio/Dok'
               'umentit/Pankkiviivakoodi-opas.pdf')
    )

    @api.multi
    def invoice_print(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        assert len(self) == 1, \
            'This option should only be used for a single id at a time.'
        # noinspection PyAttributeOutsideInit
        self.sent = True
        return self.env['report']\
            .get_action(self,
                        'l10n_fi_invoice.report_invoice_finnish_translate')
