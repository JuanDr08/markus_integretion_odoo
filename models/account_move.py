from __future__ import annotations

import json
import logging
from typing import Any

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

MARKUS_TIMEOUT = 10

IDENTIFICATION_TYPE_MAP = {
    'rut': 'NIT',
    'national_citizen_id': 'CC',
    'foreign_resident_card': 'CE',
    'passport': 'PASAPORTE',
    'id_card': 'TI',
    'civil_registration': 'RC',
    'foreign_colombian_card': 'TE',
    'niup_id': 'NUIP',
    'PEP': 'PEP',
    'PPT': 'PPT',
    'external_id': 'IE',
    'NIT_OTRO_PAIS': 'NIT_OTRO_PAIS',
}

TAX_LEVEL_CODE_MAP = {
    '48': 'RESPONSABLE_DE_IVA',
    '49': 'NO_RESPONSABLE_DE_IVA',
    '47': 'SIMPLIFICADO',
}

REGIMEN_MAP = {
    'O-13': 'GRAN_CONTRIBUYENTE',
    'O-15': 'AUTORRETENEDOR',
    'O-23': 'AGENTE_RETENCION_IVA',
    'O-47': 'SIMPLE',
    'R-99-PN': 'NO_APLICA',
}


def _clean_none(d: dict) -> dict:
    """Remove keys with None values from a dict, recursively."""
    cleaned = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            v = _clean_none(v)
        if isinstance(v, list):
            v = [_clean_none(i) if isinstance(i, dict) else i for i in v if i is not None]
        cleaned[k] = v
    return cleaned


def _map_tax_category(tax_group_name: str) -> str:
    name = (tax_group_name or '').upper()
    if name.startswith('INC') or 'CONSUMO' in name:
        return 'IMP_CONSUMO'
    if name.startswith('IVA') or 'IVA' in name:
        return 'IVA'
    return 'IVA'


def _map_retention_category(tax_group_name: str) -> str:
    name = (tax_group_name or '').upper()
    if 'ICA' in name:
        return 'RET_ICA'
    if 'IVA' in name:
        return 'RET_IVA'
    return 'RET_FUENTE'


def _is_retention(tax: Any) -> bool:
    name = (tax.tax_group_id.name or '').upper()
    return name.startswith('R ') or 'RET' in name or 'RETENCION' in name


class AccountMove(models.Model):
    _inherit = 'account.move'

    markus_sync_status: str = fields.Selection(
        selection=[
            ('draft', 'Pendiente/Borrador'),
            ('sent', 'Enviado a Markus'),
            ('error', 'Error'),
        ],
        string="Estado Markus",
        default='draft',
        readonly=True,
        copy=False,
    )
    markus_cufe: str = fields.Char(
        string="ID Documento Markus",
        readonly=True,
        copy=False,
        help="Identificador único del documento en la plataforma Markus (documentId).",
    )
    markus_pdf_url: str = fields.Char(
        string="Referencia Markus",
        readonly=True,
        copy=False,
        help="Referencia interna asignada por Markus al documento.",
    )
    markus_error_message: str = fields.Text(
        string="Mensaje de Error",
        readonly=True,
        copy=False,
    )

    def _post(self, soft: bool = True) -> 'AccountMove':
        posted = super()._post(soft=soft)

        for invoice in posted.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'posted'
        ):
            payload = invoice._prepare_markus_payload()
            invoice._send_to_markus(payload)

        return posted

    def action_retry_markus(self) -> None:
        self.ensure_one()
        payload = self._prepare_markus_payload()
        self._send_to_markus(payload)

    def _resolve_payment_means(self) -> tuple[str, str]:
        self.ensure_one()
        pos_orders = self.sudo().pos_order_ids if hasattr(self, 'pos_order_ids') else None
        if pos_orders:
            payments = pos_orders.payment_ids.filtered(lambda p: not p.is_change)
            if payments:
                pm_journal = payments[:1].payment_method_id.journal_id
                if pm_journal:
                    return (
                        pm_journal.markus_payment_means or 'CASH',
                        pm_journal.markus_payment_means_type or 'DEBITO',
                    )
        journal = self.journal_id
        return (
            journal.markus_payment_means or 'CASH',
            journal.markus_payment_means_type or 'DEBITO',
        )

    def _prepare_markus_payload(self) -> dict[str, Any]:
        self.ensure_one()
        company = self.company_id
        partner = self.partner_id

        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
        )

        self._validate_uom_dian_codes(product_lines)

        customer = self._build_customer_data(partner)
        items = [self._build_item_data(line) for line in product_lines]

        notes_text = html2plaintext(self.narration).strip() if self.narration else None

        payment_means, payment_means_type = self._resolve_payment_means()

        payload = {
            "externalId": self.name,
            "resolutionId": company.markus_resolution_id,
            "issueDate": str(self.invoice_date) if self.invoice_date else None,
            "dueDate": str(self.invoice_date_due) if self.invoice_date_due else None,
            "paymentMeans": payment_means,
            "paymentMeansType": payment_means_type,
            "orderReference": self.ref or None,
            "notes": [notes_text] if notes_text else None,
            "customer": customer,
            "items": items,
        }

        return _clean_none(payload)

    def _validate_uom_dian_codes(self, lines: Any) -> None:
        missing_uoms = []
        for line in lines:
            uom = line.product_uom_id
            if uom and not uom.markus_dian_code:
                uom_name = uom.name
                if uom_name not in missing_uoms:
                    missing_uoms.append(uom_name)
        if missing_uoms:
            raise UserError(_(
                "Las siguientes unidades de medida no tienen código DIAN configurado: %s. "
                "Configure el campo 'Código DIAN' en cada unidad de medida desde "
                "Ajustes > Técnico > Unidades de medida.",
                ', '.join(missing_uoms),
            ))

    def _build_customer_data(self, partner: Any) -> dict[str, Any]:
        id_type = self._map_identification_type(partner)

        first_name = None
        last_name = None
        if not partner.is_company:
            parts = (partner.name or '').split()
            first_name = parts[0] if parts else partner.name
            last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

        verification_digit = getattr(partner, 'l10n_co_verification_code', None)

        return {
            "partyType": "PERSONA_JURIDICA" if partner.is_company else "PERSONA_NATURAL",
            "identificationType": id_type,
            "identification": partner.vat,
            "taxLevelCode": TAX_LEVEL_CODE_MAP.get(partner.markus_regimen_fiscal, 'NO_RESPONSABLE_DE_IVA'),
            "email": partner.email,
            "regimen": REGIMEN_MAP.get(partner.markus_responsabilidad) or None,
            "phone": partner.phone or partner.mobile or None,
            "companyName": partner.name if partner.is_company else None,
            "firstName": first_name,
            "lastName": last_name,
            "verificationDigit": verification_digit or None,
            "department": partner.state_id.name if partner.state_id else None,
            "city": partner.city or None,
            "address": partner.street or None,
            "countryCode": partner.country_id.code if partner.country_id else "CO",
        }

    def _map_identification_type(self, partner: Any) -> str:
        id_type_record = getattr(partner, 'l10n_latam_identification_type_id', None)
        if id_type_record:
            doc_code = getattr(id_type_record, 'l10n_co_document_code', None)
            if doc_code and doc_code in IDENTIFICATION_TYPE_MAP:
                return IDENTIFICATION_TYPE_MAP[doc_code]
            name_upper = (id_type_record.name or '').upper()
            if 'NIT' in name_upper:
                return 'NIT'
            if 'CIUDADAN' in name_upper:
                return 'CC'
            if 'EXTRANJER' in name_upper:
                return 'CE'
            if 'PASAPORTE' in name_upper:
                return 'PASAPORTE'
        return 'NIT'

    def _build_item_data(self, line: Any) -> dict[str, Any]:
        price_after_discount = line.price_unit * (1 - line.discount / 100)

        taxes = []
        retentions = []
        for tax in line.tax_ids:
            if _is_retention(tax):
                retentions.append({
                    "taxCategory": _map_retention_category(tax.tax_group_id.name),
                    "taxRate": abs(tax.amount),
                    "baseAmount": line.price_subtotal,
                    "amount": round(line.price_subtotal * abs(tax.amount) / 100, 2),
                })
            else:
                tax_entry: dict[str, Any] = {
                    "taxCategory": _map_tax_category(tax.tax_group_id.name),
                    "baseAmount": line.price_subtotal,
                }
                if tax.amount_type in ('percent', 'division'):
                    tax_entry["taxRate"] = tax.amount
                else:
                    tax_entry["taxAmount"] = tax.amount
                taxes.append(tax_entry)

        dian_code = line.product_uom_id.markus_dian_code if line.product_uom_id else '94'

        item: dict[str, Any] = {
            "sku": (line.product_id.default_code or str(line.product_id.id)) if line.product_id else "MISC",
            "description": line.name or '',
            "quantity": line.quantity,
            "price": round(price_after_discount, 2),
            "measuringUnit": dian_code,
        }

        if line.discount:
            item["originalPrice"] = line.price_unit
            item["discountRate"] = line.discount

        if taxes:
            item["taxes"] = taxes
        if retentions:
            item["retentions"] = retentions

        return item

    def _send_to_markus(self, payload: dict[str, Any]) -> None:
        self.ensure_one()
        company = self.company_id

        errors = []
        if not company.markus_api_host:
            errors.append(_("Host API Markus"))
        if not company.markus_api_token:
            errors.append(_("Token de API"))
        if not company.markus_resolution_id:
            errors.append(_("Resolución DIAN (UUID)"))
        if errors:
            raise UserError(_(
                "Configuración incompleta de Markus para la empresa '%s'. "
                "Faltan: %s",
                company.name,
                ', '.join(errors),
            ))

        partner = self.partner_id
        if not partner.vat:
            raise UserError(_(
                "El cliente '%s' no tiene número de identificación (NIT/CC).",
                partner.name,
            ))
        if not partner.email:
            raise UserError(_(
                "El cliente '%s' no tiene email configurado. "
                "La API de Markus lo requiere.",
                partner.name,
            ))

        host = company.markus_api_host.rstrip('/')
        url = f"{host}/api/v2/integrations/odoo/invoices"
        headers = {
            "Authorization": f"Bearer {company.markus_api_token}",
            "Content-Type": "application/json",
        }

        _logger.info(
            "Markus API → POST %s | Invoice: %s | Payload: %s",
            url, self.name, json.dumps(payload, default=str, ensure_ascii=False),
        )

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=MARKUS_TIMEOUT,
            )
            response.raise_for_status()
        except requests.Timeout:
            _logger.error("Markus API timeout for invoice %s", self.name)
            raise UserError(_(
                "El servicio de Markus no respondió a tiempo (%ss). "
                "Verifique la conectividad e intente nuevamente.",
                MARKUS_TIMEOUT,
            ))
        except requests.ConnectionError:
            _logger.error("Markus API connection error for invoice %s", self.name)
            raise UserError(_(
                "No se pudo conectar con el servicio de Markus (%s). "
                "Verifique la conectividad a internet.",
                host,
            ))
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else 0
            body = exc.response.text if exc.response is not None else str(exc)
            _logger.error(
                "Markus API ← HTTP %s | Invoice: %s | Response: %s",
                status_code, self.name, body,
            )
            error_detail = body
            try:
                error_json = exc.response.json()
                msg = error_json.get('message', body)
                if isinstance(msg, list):
                    error_detail = '; '.join(msg)
                else:
                    error_detail = str(msg)
            except Exception:
                pass
            raise UserError(_(
                "Error al enviar factura a Markus (HTTP %s): %s",
                status_code, error_detail,
            ))
        except Exception as exc:
            _logger.exception("Unexpected Markus API error for invoice %s", self.name)
            raise UserError(_(
                "Error inesperado al contactar Markus: %s", exc,
            ))

        data = response.json()
        _logger.info(
            "Markus API ← OK | Invoice: %s | Response: %s",
            self.name, json.dumps(data, default=str, ensure_ascii=False),
        )

        self.write({
            'markus_sync_status': 'sent',
            'markus_cufe': data.get('documentId', ''),
            'markus_pdf_url': data.get('reference', ''),
        })
