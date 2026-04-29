# app/services/preventive_pdf_generator.py
from datetime import datetime
from app.services.pdf_generator import WorkOrderPDF, normalize


class PreventiveWorkOrderPDF(WorkOrderPDF):
    """
    Generador de PDF para Órdenes de Trabajo Preventivas.
    Hereda todo el formato (encabezado, pie, marca de agua) de WorkOrderPDF
    y solo cambia el contenido principal.
    """

    def draw_report(self, work_order=None, preview_mode=False):
        self.add_page()

        # Título
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 51, 102)

        if preview_mode:
            title = 'Vista previa de reporte preventivo'
        else:
            title = f'Reporte de Mantenimiento Preventivo - OT #{work_order.id}'

        self.cell(0, 10, normalize(title), 0, 1, 'C')
        self.ln(6)

        if preview_mode:
            # Datos de ejemplo para previsualización
            table_rows = [
                ('Equipo', 'Compresor de Aire'),
                ('Código', 'COM-001'),
                ('Técnico', 'Juan Pérez'),
                ('Fecha ejecución', datetime.now().strftime('%d/%m/%Y %H:%M')),
                ('Duración total', '45 minutos'),
            ]
            activities_data = [
                ('Lubricación', '12 min', 'Sí', 'N/A'),
                ('Inspección visual', '8 min', 'Sí', 'N/A'),
                ('Limpieza de filtros', '25 min', 'Sí', 'N/A'),
            ]
            comments = 'Se realizaron todas las actividades según lo planificado.'
        else:
            wo = work_order
            # Obtener el log de ejecución preventiva
            exec_log = wo.preventive_execution_log if hasattr(wo, 'preventive_execution_log') else None
            total_min = exec_log.total_duration_min if exec_log else 0
            comments = exec_log.general_comments if exec_log else ''

            table_rows = [
                ('Equipo', wo.equipment.name if wo.equipment else 'N/A'),
                ('Código', wo.equipment.code if wo.equipment else 'N/A'),
                ('Técnico', wo.assigned_to.username if wo.assigned_to else 'No asignado'),
                ('Fecha ejecución', wo.created_at.strftime('%d/%m/%Y %H:%M') if wo.created_at else 'N/A'),
                ('Duración total', f'{total_min} minutos' if total_min else 'N/A'),
            ]

            # Actividades desde measurements (JSON)
            activities_data = []
            if wo.measurements:
                for act_name, act_data in wo.measurements.items():
                    completed = 'Sí' if act_data.get('completed') else 'No'
                    duration_sec = act_data.get('duration_seconds', 0)
                    duration_min = round(duration_sec / 60, 1) if duration_sec else 0
                    measured = f"{act_data.get('measured_value', '')} {act_data.get('unit', '')}".strip() or 'N/A'
                    activities_data.append((act_name, f'{duration_min} min', completed, measured))

        # Tabla general
        self.draw_table(table_rows)

        # Tabla de actividades
        self.section_title('Actividades realizadas')
        if activities_data:
            self._draw_activities_table(activities_data)
        else:
            self._draw_wrapped_paragraph('No se registraron actividades.', width=self.epw)

        # Comentarios
        if comments:
            self.section_title('Comentarios')
            self._draw_wrapped_paragraph(comments, width=self.epw)

    def _draw_activities_table(self, activities):
        """Dibuja una tabla con Actividad, Tiempo, Completado, Medición"""
        col_widths = [80, 25, 25, 50]  # mm
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(220, 220, 220)
        self.set_draw_color(150, 150, 150)

        # Cabecera
        x_start = self.l_margin
        y = self.get_y()
        headers = ['Actividad', 'Tiempo', 'Completado', 'Medición']
        for i, header in enumerate(headers):
            self.set_xy(x_start, y)
            self.cell(col_widths[i], 8, normalize(header), 1, 0, 'C', 1)
            x_start += col_widths[i]
        self.ln(8)

        # Filas
        self.set_font('Helvetica', '', 9)
        fill = False
        for act_name, duration, completed, measured in activities:
            x_start = self.l_margin
            y = self.get_y()
            if y + 8 > self.page_break_trigger:
                self.add_page()
                # Re-dibujar cabecera
                self.set_font('Helvetica', 'B', 9)
                x_start = self.l_margin
                for i, header in enumerate(headers):
                    self.set_xy(x_start, self.get_y())
                    self.cell(col_widths[i], 8, normalize(header), 1, 0, 'C', 1)
                    x_start += col_widths[i]
                self.ln(8)
                x_start = self.l_margin
                self.set_font('Helvetica', '', 9)

            self.set_xy(x_start, self.get_y())
            self.cell(col_widths[0], 6, normalize(act_name[:60]), 1, 0, 'L', fill)
            x_start += col_widths[0]
            self.set_xy(x_start, self.get_y())
            self.cell(col_widths[1], 6, normalize(duration), 1, 0, 'C', fill)
            x_start += col_widths[1]
            self.set_xy(x_start, self.get_y())
            self.cell(col_widths[2], 6, normalize(completed), 1, 0, 'C', fill)
            x_start += col_widths[2]
            self.set_xy(x_start, self.get_y())
            self.cell(col_widths[3], 6, normalize(measured[:40]), 1, 0, 'L', fill)

            self.ln(6)
            fill = not fill
        self.ln(4)