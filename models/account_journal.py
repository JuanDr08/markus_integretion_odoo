from __future__ import annotations

from odoo import fields, models

MARKUS_PAYMENT_MEANS = [
    ('CASH', 'Efectivo'),
    ('CREDIT_CARD', 'Tarjeta de crédito'),
    ('DEBIT_CARD', 'Tarjeta de débito'),
    ('BANK_TRANSFER', 'Transferencia bancaria'),
    ('CHEQUE', 'Cheque'),
    ('CREDIT_ACH', 'ACH crédito'),
    ('DEBIT_ACH', 'ACH débito'),
    ('CREDIT_AHORRO', 'Crédito ahorro'),
    ('DEBIT_AHORRO', 'Débito ahorro'),
    ('CREDIT_TRANSFER', 'Transferencia crédito'),
    ('DEBIT_TRANSFER', 'Transferencia débito'),
    ('CREDIT_BANK_TRANSFER', 'Transferencia bancaria crédito'),
    ('DEBIT_BANK_TRANSFER', 'Transferencia bancaria débito'),
    ('DEBIT_INTERBANK_TRANSFER', 'Transferencia interbancaria débito'),
    ('MUTUAL_AGREEMENT', 'Acuerdo mutuo'),
    ('GIRO_URGENTE', 'Giro urgente'),
    ('CHEQUE_LOCAL_TRANSFERIBLE', 'Cheque local transferible'),
    ('INSTRUMENTO_NO_DEFINIDO', 'Instrumento no definido'),
    ('PAGO_COMERCIAL_URGENTE', 'Pago comercial urgente'),
    ('CONCENTRACION_EFECTIVO_CCD', 'Concentración efectivo CCD'),
    ('GIRO_REFERENCIADO', 'Giro referenciado'),
    ('OTHER', 'Otro'),
]


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    markus_payment_means: str = fields.Selection(
        selection=MARKUS_PAYMENT_MEANS,
        string="Método de Pago DIAN",
        default='CASH',
        help="Método de pago que se envía a la DIAN a través de Markus "
             "para las facturas registradas en este diario.",
    )
    markus_payment_means_type: str = fields.Selection(
        selection=[
            ('DEBITO', 'Contado / Débito'),
            ('CREDITO', 'Crédito'),
        ],
        string="Tipo Método de Pago DIAN",
        default='DEBITO',
        help="Indica si el pago es de contado (DEBITO) o a crédito (CREDITO).",
    )
