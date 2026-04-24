import os
from flask import current_app
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from datetime import datetime
from app.models.report_config import ReportConfig
from app.models.setting import Setting
from app.utils.file_utils import ensure_dir, sanitize_filename


def generate_work_order_pdf(work_order):
    """Genera PDF usando ReportLab (sin dependencias externas)"""

    # Obtener configuración
    config = ReportConfig.get_config()
    company_name = Setting.get('company_name', 'Mi Empresa')
    company_logo = Setting.get('company_logo', '')

    # Definir ruta del archivo
    equipment_name = work_order.equipment.name if work_order.equipment else "sin_equipo"
    safe_name = sanitize_filename(equipment_name)
    base_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'reports', safe_name)
    ensure_dir(base_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"OT_{work_order.id}_{timestamp}.pdf"
    filepath = os.path.join(base_dir, filename)

    # Crear documento PDF
    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch)

    styles = getSampleStyleSheet()
    story = []

    # Estilos personalizados
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                 alignment=TA_CENTER, fontSize=16, spaceAfter=20)
    header_style = ParagraphStyle('Header', parent=styles['Normal'],
                                  alignment=TA_CENTER, fontSize=10, textColor=colors.gray)
    normal_style = styles['Normal']

    # Logo de empresa
    if config.use_company_logo and company_logo:
        logo_path = os.path.join(current_app.root_path, 'static', company_logo)
        if os.path.exists(logo_path):
            try:
                img = Image(logo_path, width=1 * inch, height=1 * inch)
                story.append(img)
                story.append(Spacer(1, 0.1 * inch))
            except:
                pass

    # Nombre de empresa
    if config.use_company_name:
        story.append(Paragraph(company_name, title_style))
        story.append(Spacer(1, 0.2 * inch))

    # Título del reporte
    story.append(Paragraph(f"Reporte de Orden de Trabajo #{work_order.id}", title_style))
    story.append(Spacer(1, 0.3 * inch))

    # Datos principales
    data = [
        ["Fecha de cierre:", datetime.now().strftime('%d/%m/%Y %H:%M')],
        ["Equipo:", work_order.equipment.name if work_order.equipment else 'N/A'],
        ["Código:", work_order.equipment.code if work_order.equipment else 'N/A'],
        ["Técnico asignado:", work_order.assigned_to.username if work_order.assigned_to else 'No asignado'],
        ["Creado por:", work_order.created_by.username if work_order.created_by else 'Sistema'],
        ["Estado:", work_order.status.upper()],
    ]

    if work_order.start_date:
        data.append(["Fecha inicio:", work_order.start_date.strftime('%d/%m/%Y %H:%M')])
    if work_order.completion_date:
        data.append(["Fecha fin:", work_order.completion_date.strftime('%d/%m/%Y %H:%M')])
    if work_order.downtime_hours:
        data.append(["Tiempo parada:", f"{work_order.downtime_hours} horas"])

    table = Table(data, colWidths=[1.5 * inch, 4 * inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3 * inch))

    # Descripción del problema
    story.append(Paragraph("<b>Problema reportado:</b>", styles['Heading4']))
    story.append(Paragraph(work_order.problem_description or 'N/A', normal_style))
    story.append(Spacer(1, 0.2 * inch))

    # Información técnica
    if work_order.failure_type or work_order.root_cause or work_order.work_performed:
        story.append(Paragraph("<b>Información técnica:</b>", styles['Heading4']))
        if work_order.failure_type:
            story.append(Paragraph(f"<b>Tipo de falla:</b> {work_order.failure_type}", normal_style))
        if work_order.root_cause:
            story.append(Paragraph(f"<b>Causa raíz:</b> {work_order.root_cause}", normal_style))
        if work_order.work_performed:
            story.append(Paragraph(f"<b>Trabajo realizado:</b> {work_order.work_performed}", normal_style))
        if work_order.parts_used:
            story.append(Paragraph(f"<b>Repuestos:</b> {work_order.parts_used}", normal_style))
        story.append(Spacer(1, 0.2 * inch))

    # Notas de cierre
    if work_order.resolution_summary:
        story.append(Paragraph("<b>Notas de cierre:</b>", styles['Heading4']))
        story.append(Paragraph(work_order.resolution_summary, normal_style))
        story.append(Spacer(1, 0.2 * inch))

    # Construir PDF
    doc.build(story)

    # Obtener tamaño
    file_size = os.path.getsize(filepath)
    relative_path = os.path.join('uploads', 'reports', safe_name, filename).replace('\\', '/')

    return {
        'file_path': relative_path,
        'filename': filename,
        'file_size': file_size,
        'absolute_path': filepath
    }