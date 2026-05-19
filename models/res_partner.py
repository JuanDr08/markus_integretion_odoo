from __future__ import annotations

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    markus_regimen_fiscal: str = fields.Selection(
        selection=[
            ('48', 'Responsable de IVA'),
            ('49', 'No responsable de IVA'),
            ('47', 'Régimen Simple'),
        ],
        string="Régimen Fiscal",
        help="Régimen fiscal del contacto según clasificación DIAN.",
    )
    markus_responsabilidad: str = fields.Selection(
        selection=[
            ('O-13', 'Gran contribuyente'),
            ('O-15', 'Autorretenedor'),
            ('O-23', 'Agente de retención IVA'),
            ('O-47 ', 'Régimen simple de tributación'),
            ('R-99-PN', 'No Responsable'),
        ],
        string="Responsabilidad Fiscal",
        help="Responsabilidad fiscal del contacto según clasificación DIAN.",
    )
