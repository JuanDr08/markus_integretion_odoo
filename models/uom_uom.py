from __future__ import annotations

from odoo import fields, models


class UomUom(models.Model):
    _inherit = 'uom.uom'

    markus_dian_code: str = fields.Char(
        string="Código DIAN",
        help="Código DIAN de la unidad de medida para facturación electrónica "
             "(ej: 94, KGM, LTR, SER, HUR, MTR, CMT, SET, NAR).",
    )
