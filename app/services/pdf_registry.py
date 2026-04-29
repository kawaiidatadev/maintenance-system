# app/services/pdf_registry.py
from app.models.pdf_template import PDFTemplate


class PDFRegistry:
    """Registro central de todos los tipos de PDF disponibles"""

    _templates = {}

    @classmethod
    def register(cls, key, name, description='', generator_class=None):
        """Registra un tipo de PDF en memoria y en BD"""
        cls._templates[key] = {
            'name': name,
            'description': description,
            'generator_class': generator_class
        }
        # También asegurar que existe en BD
        from app import db
        template = PDFTemplate.query.filter_by(key=key).first()
        if not template:
            template = PDFTemplate(key=key, name=name, description=description)
            db.session.add(template)
            db.session.commit()
        return template

    @classmethod
    def get_template(cls, key):
        return cls._templates.get(key)

    @classmethod
    def get_all(cls):
        return cls._templates

    @classmethod
    def get_generator(cls, key, config, company_name, company_logo):
        """Instancia el generador adecuado para este tipo de PDF"""
        template_info = cls._templates.get(key)
        if template_info and template_info['generator_class']:
            return template_info['generator_class'](config, company_name, company_logo)
        # Fallback a generator genérico
        from app.services.pdf_generator import BaseReportPDF
        return BaseReportPDF(config, company_name, company_logo)


# ============================================
# FUNCIÓN PARA REGISTRAR TODOS LOS TIPOS DE PDF
# ============================================
def register_pdf_types():
    """Registra todos los tipos de PDF disponibles en el sistema"""
    from app.services.pdf_generator import WorkOrderPDF
    from app.services.preventive_pdf_generator import PreventiveWorkOrderPDF

    PDFRegistry.register('work_order', 'Orden de Trabajo (Correctivo)',
                         'Reporte estándar para órdenes correctivas',
                         generator_class=WorkOrderPDF)
    PDFRegistry.register('preventive_work_order', 'Orden de Trabajo Preventivo',
                         'Reporte para mantenimiento preventivo con checklist',
                         generator_class=PreventiveWorkOrderPDF)