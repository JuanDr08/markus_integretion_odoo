from __future__ import annotations

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    markus_tenant_id: str = fields.Char(
        string="ID de Empresa en Markus",
        help="Identificador único de esta empresa en la plataforma Markus. "
             "Se obtiene desde el panel de administración de Markus.",
    )
    markus_api_token: str = fields.Char(
        string="Token de API",
        help="Token de autenticación para consumir los endpoints de la API Markus. "
             "Mantenerlo confidencial.",
    )
    markus_api_host: str = fields.Char(
        string="Host API Markus",
        help="URL base del servidor Markus sin trailing slash "
             "(ej: https://api.markuscloud.com).",
    )
    markus_resolution_id: str = fields.Char(
        string="Resolución DIAN (UUID)",
        help="UUID de la resolución de facturación DIAN activa en Markus. "
             "Se obtiene desde el panel de resoluciones en Markus.",
    )
