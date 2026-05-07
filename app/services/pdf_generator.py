import os
import io
import tempfile
from datetime import datetime
from flask import current_app
from fpdf import FPDF

from app.models.report_config import ReportConfig
from app.models.setting import Setting
from app.utils.file_utils import ensure_dir, sanitize_filename
from app.models.pdf_template import PDFTemplate
from app.models.pdf_template_config import PDFTemplateConfig
from app.services.pdf_registry import PDFRegistry
from app.utils import format_datetime


# Normalización de caracteres para fuentes estándar
_REPS = {
    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
    'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
    'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U',
    'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
    'ç': 'c', 'Ç': 'C'
}


def normalize(txt):
    if not txt:
        return ''
    txt = str(txt)
    for src, dst in _REPS.items():
        txt = txt.replace(src, dst)
    return txt


class WorkOrderPDF(FPDF):
    """
    PDF profesional para órdenes de trabajo.
    """

    def __init__(self, config, company_name, company_logo):
        super().__init__()
        self.core_fonts_encoding = 'utf-8'
        self.config = config
        self.company_name = company_name
        self.company_logo = company_logo

        # Configuración base
        self.left_margin = 20
        self.top_margin = 25
        self.right_margin = 20
        self.bottom_margin = 20

        self.set_margins(self.left_margin, self.top_margin, self.right_margin)
        self.set_auto_page_break(True, margin=self.bottom_margin)

        self.body_font = 'Helvetica'
        self.body_size = 10
        self.line_h = 5.2

        # Inicializar diccionario para transparencias
        self._extgstates = {}

    # ------------------------------------------------------------------
    # Soporte de transparencia (opacidad)
    # ------------------------------------------------------------------
    def set_alpha(self, alpha, bm='Normal'):
        """Implementa transparencia en FPDF (para marcas de agua)"""
        if alpha < 0:
            alpha = 0
        if alpha > 1:
            alpha = 1

        gs = len(self._extgstates) + 1
        self._extgstates[gs] = {'ca': alpha, 'CA': alpha, 'BM': bm}
        self._out(f'/GS{gs} gs')

    # ------------------------------------------------------------------
    # Marca de agua (fondo) con opacidad y procesamiento PIL
    # ------------------------------------------------------------------
    def _draw_watermark(self):
        """Dibuja logo y nombre de la empresa como marca de agua de fondo, muy tenue"""
        if not self.config.use_company_logo and not self.config.use_company_name:
            return

        # Aplicar transparencia (8%)
        self.set_alpha(0.08)

        # Logo centrado
        if self.config.use_company_logo and self.company_logo:
            logo_path = os.path.join(current_app.root_path, 'static', self.company_logo)
            if os.path.exists(logo_path):
                try:
                    from PIL import Image, ImageEnhance

                    img = Image.open(logo_path).convert("RGBA")

                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(0.6)

                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(1.4)

                    alpha_channel = img.split()[3]
                    alpha_channel = alpha_channel.point(lambda p: int(p * 0.25))
                    img.putalpha(alpha_channel)

                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        img.save(tmp.name)
                        tmp_path = tmp.name

                    w, h = img.size
                    max_w = 55
                    if w > max_w:
                        ratio = max_w / w
                        w = max_w
                        h = h * ratio
                    x = (self.w - w) / 2
                    y = (self.h - h) / 2 - 25
                    self.image(tmp_path, x=x, y=y, w=w)
                    os.unlink(tmp_path)
                except Exception as e:
                    print(f"Error procesando logo: {e}")
                    img = Image.open(logo_path)
                    w, h = img.size
                    max_w = 55
                    if w > max_w:
                        ratio = max_w / w
                        w = max_w
                        h = h * ratio
                    x = (self.w - w) / 2
                    y = (self.h - h) / 2 - 25
                    self.image(logo_path, x=x, y=y, w=w)

        if self.config.use_company_name and self.company_name:
            self.set_font('Helvetica', 'B', 22)
            self.set_text_color(200, 200, 200)
            self.set_xy(0, (self.h / 2) + 25)
            self.cell(self.w, 12, normalize(self.company_name), 0, 0, 'C')

        self.set_alpha(1.0)
        self.set_text_color(0, 0, 0)

    # ------------------------------------------------------------------
    # Utilidades de texto y espacio
    # ------------------------------------------------------------------
    def _wrap_text(self, text, width, font_style='', font_size=None):
        if font_size is None:
            font_size = self.body_size

        text = normalize(text)
        if text == '':
            return ['']

        old_style = self.font_style
        old_size = self.font_size_pt

        self.set_font(self.body_font, font_style, font_size)

        lines = []
        paragraphs = text.split('\n')

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph == '':
                lines.append('')
                continue

            words = paragraph.split()
            current = ''

            for word in words:
                test = word if current == '' else f'{current} {word}'
                if self.get_string_width(test) <= width:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word

            if current:
                lines.append(current)

        self.set_font(self.body_font, old_style, old_size)
        return lines

    def _ensure_space(self, height_needed):
        if self.get_y() + height_needed > self.page_break_trigger:
            self.add_page()

    def _draw_wrapped_paragraph(self, text, width=None, font_style='', font_size=None, line_h=None, x=None):
        if width is None:
            width = self.epw
        if font_size is None:
            font_size = self.body_size
        if line_h is None:
            line_h = self.line_h
        if x is None:
            x = self.l_margin

        lines = self._wrap_text(text, width, font_style=font_style, font_size=font_size)
        self.set_font(self.body_font, font_style, font_size)

        for line in lines:
            self._ensure_space(line_h)
            self.set_x(x)
            self.cell(width, line_h, normalize(line), 0, 1, 'L')

    def _draw_key_value(self, label, value, label_w=40, value_font_size=10, label_font_size=10,
                        line_h=None, gap=2):
        if line_h is None:
            line_h = self.line_h

        label = normalize(label).rstrip(':') + ':'
        value = normalize(value)

        x0 = self.l_margin
        y0 = self.get_y()

        value_w = self.epw - label_w - gap

        label_lines = self._wrap_text(label, label_w, font_style='B', font_size=label_font_size)
        value_lines = self._wrap_text(value, value_w, font_style='', font_size=value_font_size)

        row_h = max(len(label_lines), len(value_lines)) * line_h
        self._ensure_space(row_h)

        self.set_xy(x0, self.get_y())
        self.set_font(self.body_font, 'B', label_font_size)
        self.set_text_color(0, 51, 102)
        for i, line in enumerate(label_lines):
            if i > 0:
                self.ln(line_h)
                self.set_x(x0)
            self.cell(label_w, line_h, line, 0, 0, 'L')

        self.set_xy(x0 + label_w + gap, y0)
        self.set_font(self.body_font, '', value_font_size)
        self.set_text_color(0, 0, 0)
        for i, line in enumerate(value_lines):
            if i > 0:
                self.ln(line_h)
                self.set_x(x0 + label_w + gap)
            self.cell(value_w, line_h, line, 0, 0, 'L')

        self.set_y(y0 + row_h)

    # ------------------------------------------------------------------
    # Encabezado
    # ------------------------------------------------------------------
    def header(self):
        self._draw_watermark()
        self.set_y(15)

        x_left = 20
        if self.config.header_left_img:
            img_path = os.path.join(current_app.root_path, 'static', self.config.header_left_img)
            if os.path.exists(img_path):
                img_width = getattr(self.config, 'header_left_img_width', 25)
                self.image(img_path, x=x_left, y=self.get_y(), w=img_width)
        elif self.config.header_left:
            self.set_font('Helvetica', '', 8)
            self.set_xy(x_left, self.get_y())
            self.multi_cell(55, 4, normalize(self.config.header_left), 0, 'L')

        x_center = self.w / 2
        if self.config.header_center_img:
            img_path = os.path.join(current_app.root_path, 'static', self.config.header_center_img)
            if os.path.exists(img_path):
                img_width = getattr(self.config, 'header_center_img_width', 30)
                self.image(img_path, x=x_center - img_width / 2, y=15, w=img_width)
        elif self.config.header_center:
            self.set_font('Helvetica', '', 8)
            self.set_xy(x_center - 40, 15)
            self.multi_cell(80, 4, normalize(self.config.header_center), 0, 'C')

        x_right = self.w - 20
        if self.config.header_right_img:
            img_path = os.path.join(current_app.root_path, 'static', self.config.header_right_img)
            if os.path.exists(img_path):
                img_width = getattr(self.config, 'header_right_img_width', 25)
                self.image(img_path, x=x_right - img_width, y=15, w=img_width)
        elif self.config.header_right:
            self.set_font('Helvetica', '', 8)
            self.set_xy(x_right - 65, 15)
            self.multi_cell(60, 4, normalize(self.config.header_right), 0, 'R')

        max_y = self.get_y()
        if self.config.header_center and not self.config.header_center_img:
            max_y = max(max_y, 30)
        if self.config.header_right and not self.config.header_right_img:
            max_y = max(max_y, 30)

        self.set_y(max_y + 8)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.set_line_width(0.2)
        self.set_y(self.get_y() + 12)

    # ------------------------------------------------------------------
    # Pie de página
    # ------------------------------------------------------------------
    def footer(self):
        footer_y = self.h - 20
        self.set_y(footer_y)

        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.set_y(self.get_y() + 4)

        x_left = 20
        x_center = self.w / 2
        x_right = self.w - 20

        if self.config.footer_left_img:
            img_path = os.path.join(current_app.root_path, 'static', self.config.footer_left_img)
            if os.path.exists(img_path):
                img_width = getattr(self.config, 'footer_left_img_width', 20)
                self.image(img_path, x=x_left, y=self.get_y(), w=img_width)
        elif self.config.footer_left:
            self.set_font('Helvetica', 'I', 7)
            self.set_text_color(80, 80, 80)
            self.set_xy(x_left, self.get_y())
            self.multi_cell(55, 4, normalize(self.config.footer_left), 0, 'L')

        if self.config.footer_center_img:
            img_path = os.path.join(current_app.root_path, 'static', self.config.footer_center_img)
            if os.path.exists(img_path):
                img_width = getattr(self.config, 'footer_center_img_width', 25)
                self.image(img_path, x=x_center - img_width / 2, y=self.get_y(), w=img_width)
        elif self.config.footer_center:
            self.set_font('Helvetica', 'I', 7)
            self.set_text_color(80, 80, 80)
            self.set_xy(x_center - 40, self.get_y())
            self.multi_cell(80, 4, normalize(self.config.footer_center), 0, 'C')

        if self.config.footer_right_img:
            img_path = os.path.join(current_app.root_path, 'static', self.config.footer_right_img)
            if os.path.exists(img_path):
                img_width = getattr(self.config, 'footer_right_img_width', 20)
                self.image(img_path, x=x_right - img_width, y=self.get_y(), w=img_width)
        elif self.config.footer_right:
            self.set_font('Helvetica', 'I', 7)
            self.set_text_color(80, 80, 80)
            self.set_xy(x_right - 60, self.get_y())
            self.multi_cell(55, 4, normalize(self.config.footer_right), 0, 'R')

        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(80, 80, 80)
        self.set_y(self.h - 10)
        self.set_x(self.w - 25)
        self.cell(20, 5, f'Pag. {self.page_no()}', 0, 0, 'R')
        self.set_text_color(0, 0, 0)

    # ------------------------------------------------------------------
    # Bloques del reporte
    # ------------------------------------------------------------------
    def section_title(self, title):
        self._ensure_space(10)
        self.ln(6)
        self.set_font('Helvetica', 'B', 11)
        self.set_fill_color(238, 242, 247)
        self.set_text_color(0, 51, 102)
        self.cell(0, 9, f' {normalize(title)} ', 0, 1, 'L', 1)
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def draw_table(self, rows):
        label_w = 45
        value_w = self.epw - label_w
        self.set_draw_color(180, 180, 180)

        for label, value in rows:
            label = normalize(label)
            value = normalize(value)

            label_lines = self._wrap_text(label, label_w, font_style='B', font_size=10)
            value_lines = self._wrap_text(value, value_w, font_style='', font_size=10)
            row_h = max(len(label_lines), len(value_lines)) * self.line_h + 2
            self._ensure_space(row_h)

            x = self.l_margin
            y = self.get_y()

            self.rect(x, y, label_w, row_h)
            self.rect(x + label_w, y, value_w, row_h)

            self.set_font('Helvetica', 'B', 10)
            self.set_text_color(0, 51, 102)
            self.set_xy(x + 1, y + 1)
            for i, line in enumerate(label_lines):
                if i > 0:
                    self.ln(self.line_h)
                    self.set_x(x + 1)
                self.cell(label_w - 2, self.line_h, line, 0, 0, 'L')

            self.set_font('Helvetica', '', 10)
            self.set_text_color(0, 0, 0)
            self.set_xy(x + label_w + 1, y + 1)
            for i, line in enumerate(value_lines):
                if i > 0:
                    self.ln(self.line_h)
                    self.set_x(x + label_w + 1)
                self.cell(value_w - 2, self.line_h, line, 0, 0, 'L')

            self.set_y(y + row_h)

        self.set_text_color(0, 0, 0)
        self.ln(6)

    def draw_technical_info(self, items):
        if not items:
            return
        self.section_title('Informacion tecnica')
        for label, value in items:
            if value:
                self._draw_key_value(label, value, label_w=40, value_font_size=10, label_font_size=10, line_h=5.2,
                                     gap=3)
        self.ln(2)

    def draw_report(self, work_order=None, preview_mode=False):
        self.add_page()

        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 51, 102)

        if preview_mode:
            title = 'Vista previa de reporte'
        else:
            title = f'Reporte de Orden de Trabajo #{work_order.id}'

        self.cell(0, 10, normalize(title), 0, 1, 'C')
        self.ln(6)

        if preview_mode:
            now_utc = datetime.utcnow()
            table_rows = [
                ('Equipo', 'Motor Electrico Principal'),
                ('Codigo', 'MOT-ELEC-001'),
                ('Tecnico asignado', 'Juan Perez'),
                ('Creado por', 'Admin'),
                ('Fecha reporte', format_datetime(now_utc)),
                ('Fecha inicio', format_datetime(now_utc)),
                ('Fecha fin', format_datetime(now_utc)),
                ('Tiempo parada', '8.5 horas'),
            ]
            problem_text = 'El motor presenta vibracion anormal y sobrecalentamiento despues de 2 horas de operacion.'
            tech_items = [
                ('Tipo de falla', 'Vibracion excesiva'),
                ('Causa raiz', 'Desgaste de rodamientos'),
                ('Trabajo realizado', 'Cambio de rodamientos y alineacion'),
                ('Repuestos', 'Rodamientos SKF 6204 (2 unidades)'),
            ]
            closing_text = 'Se realizaron pruebas de funcionamiento, el equipo opera correctamente. Se recomienda lubricacion cada 3 meses.'
        else:
            wo = work_order
            table_rows = [
                ('Equipo', wo.equipment.name if wo.equipment else 'N/A'),
                ('Codigo', wo.equipment.code if wo.equipment else 'N/A'),
                ('Tecnico asignado', wo.assigned_to.username if wo.assigned_to else 'No asignado'),
                ('Creado por', wo.created_by.username if wo.created_by else 'Sistema'),
                ('Fecha reporte', format_datetime(wo.created_at) if wo.created_at else 'N/A'),
                ('Fecha inicio', format_datetime(wo.start_date) if wo.start_date else 'N/A'),
                ('Fecha fin', format_datetime(wo.completion_date) if wo.completion_date else 'N/A'),
                ('Tiempo parada', f'{wo.downtime_hours} horas' if wo.downtime_hours else 'N/A'),
            ]
            problem_text = wo.problem_description or 'N/A'
            tech_items = [
                ('Tipo de falla', wo.failure_type),
                ('Causa raiz', wo.root_cause),
                ('Trabajo realizado', wo.work_performed),
                ('Repuestos', wo.parts_used),
            ]
            closing_text = wo.resolution_summary

        self.draw_table(table_rows)

        self.section_title('Problema reportado')
        self.set_font('Helvetica', '', 10)
        self.set_text_color(0, 0, 0)
        self._draw_wrapped_paragraph(problem_text, width=self.epw, font_style='', font_size=10, line_h=5.2, x=self.l_margin)
        self.ln(4)

        self.draw_technical_info(tech_items)

        if closing_text:
            self.section_title('Notas de cierre')
            self.set_font('Helvetica', '', 10)
            self.set_text_color(0, 0, 0)
            self._draw_wrapped_paragraph(closing_text, width=self.epw, font_style='', font_size=10, line_h=5.2, x=self.l_margin)

    def output_to_bytes(self):
        buffer = io.BytesIO()
        self.output(buffer)
        buffer.seek(0)
        return buffer


# ============================================
# FUNCIONES PRINCIPALES (FUERA DE LA CLASE)
# ============================================

def generate_work_order_pdf(work_order):
    """Genera el PDF según el tipo de orden (correctivo o preventivo)"""
    if work_order.work_type == 'preventive':
        template_key = 'preventive_work_order'
    else:
        template_key = 'work_order'

    template = PDFTemplate.get_by_key(template_key)
    if not template:
        raise Exception(f"No se encontró la plantilla '{template_key}'")

    config = PDFTemplateConfig.get_or_create(template.id)
    company_name = Setting.get('company_name', 'Mi Empresa')
    company_logo = Setting.get('company_logo', '')

    pdf = PDFRegistry.get_generator(template_key, config, company_name, company_logo)

    equipment_name = work_order.equipment.name if work_order.equipment else "sin_equipo"
    safe_name = sanitize_filename(equipment_name)
    base_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'reports', safe_name)
    ensure_dir(base_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"OT_{work_order.id}_{timestamp}.pdf"
    filepath = os.path.join(base_dir, filename)

    pdf.draw_report(work_order=work_order, preview_mode=False)
    pdf.output(filepath)

    file_size = os.path.getsize(filepath)
    relative_path = os.path.join('uploads', 'reports', safe_name, filename).replace('\\', '/')

    return {
        'file_path': relative_path,
        'filename': filename,
        'file_size': file_size,
        'absolute_path': filepath
    }


def generate_preview_pdf(template_key=None):
    """
    Genera vista previa para una plantilla específica.
    Si no se pasa template_key, usa la plantilla por defecto 'work_order'.
    """
    if template_key is None:
        template_key = 'work_order'

    template = PDFTemplate.get_by_key(template_key)
    if not template:
        raise ValueError(f"Plantilla '{template_key}' no encontrada")

    config = PDFTemplateConfig.get_or_create(template.id)
    company_name = Setting.get('company_name', 'Mi Empresa')
    company_logo = Setting.get('company_logo', '')

    pdf = PDFRegistry.get_generator(template_key, config, company_name, company_logo)
    pdf.draw_report(work_order=None, preview_mode=True)
    return pdf.output_to_bytes()