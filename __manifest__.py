{
    'name': "Markus DIAN Integration",
    'summary': "Integración con la plataforma Markus para facturación electrónica DIAN",
    'description': """
Extensión para sincronizar datos fiscales colombianos con la plataforma Markus.
Añade campos de configuración en empresa y contactos para la integración DIAN.
    """,
    'author': "Markus Apps",
    'website': "https://www.markusapps.com",
    'category': 'Accounting/Localizations',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base', 'account', 'l10n_co', 'uom'],
    'data': [
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/account_journal_views.xml',
        'views/uom_uom_views.xml',
    ],
}

