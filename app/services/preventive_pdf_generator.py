# app/services/preventive_pdf_generator.py
from datetime import datetime
from flask import current_app
from app.services.pdf_generator import WorkOrderPDF, normalize
from app.utils import format_datetime
from app.models.group_document import GroupDocument
from app.models.preventive_schedule import PreventiveSchedule


class PreventiveWorkOrderPDF(WorkOrderPDF):
    """
    Generador de PDF para Órdenes de Trabajo Preventivas.
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
            table_rows = [
                ('Equipo', 'Compresor de Aire'),
                ('Código', 'COM-001'),
                ('Técnico asignado', 'Juan Pérez'),
                ('Creado por', 'Admin'),
                ('Fecha creación', format_datetime(datetime.utcnow())),
                ('Fecha programada', '15/05/2026'),
                ('Frecuencia', 'Cada 6 meses'),
                ('Fecha ejecución', format_datetime(datetime.utcnow())),
                ('Cerrado por', 'Juan Pérez'),
                ('Fecha cierre', format_datetime(datetime.utcnow())),
                ('Duración total', '45 minutos'),
            ]
            activities_data = [
                ('Lubricación', '12 min', 'Sí', 'N/A'),
                ('Inspección visual', '8 min', 'Sí', 'N/A'),
                ('Limpieza de filtros', '25 min', 'Sí', 'N/A'),
            ]
            comments = 'Se realizaron todas las actividades según lo planificado.'
            docs = []
        else:
            wo = work_order

            # Obtener log de ejecución (ahora sí existe la relación)
            exec_log = wo.preventive_execution_log
            total_min = exec_log.duration_minutes if exec_log else 0
            comments = exec_log.notes if exec_log else ''

            # Obtener schedule y grupo para adjuntos
            schedule = None
            group = None
            if wo.preventive_schedule_id:
                schedule = PreventiveSchedule.query.get(wo.preventive_schedule_id)
                if schedule:
                    group = schedule.group

            # Obtener metadata del measurements
            metadata = wo.measurements.get('_metadata', {}) if wo.measurements else {}
            scheduled_date = metadata.get('scheduled_date', 'N/A')
            frequency_display = metadata.get('freq_display', 'N/A')

            # Fallback si no hay metadata
            if schedule and schedule.next_due_date and scheduled_date == 'N/A':
                scheduled_date = format_datetime(schedule.next_due_date)
            if group and frequency_display == 'N/A':
                frequency_display = group.frequency_suggested

            table_rows = [
                ('Equipo', wo.equipment.name if wo.equipment else 'N/A'),
                ('Código', wo.equipment.code if wo.equipment else 'N/A'),
                ('Técnico asignado', wo.assigned_to.username if wo.assigned_to else 'No asignado'),
                ('Creado por', wo.created_by.username if wo.created_by else 'Sistema'),
                ('Fecha creación', format_datetime(wo.created_at) if wo.created_at else 'N/A'),
                ('Fecha programada', scheduled_date),
                ('Frecuencia', frequency_display),
                ('Fecha ejecución', format_datetime(wo.start_date) if wo.start_date else 'N/A'),
                ('Cerrado por', wo.closed_by.username if wo.closed_by else 'No registrado'),
                ('Fecha cierre', format_datetime(wo.closed_at) if wo.closed_at else 'N/A'),
                ('Duración total', f'{total_min} minutos' if total_min else 'N/A'),
            ]

            # Actividades desde measurements
            activities_data = []
            if wo.measurements:
                for act_id, act_data in wo.measurements.items():
                    if act_id == '_metadata':
                        continue
                    act_name = act_data.get('name', f'Actividad {act_id}')
                    completed = 'Sí' if act_data.get('completed') else 'No'
                    duration_sec = act_data.get('duration_seconds', 0)
                    duration_min = round(duration_sec / 60, 1) if duration_sec else 0
                    measured_value = act_data.get('measured_value', '')
                    unit = act_data.get('unit', '')
                    measured = f'{measured_value} {unit}'.strip() if measured_value or unit else '—'
                    activities_data.append((act_name, f'{duration_min} min', completed, measured))

            # Documentos adjuntos del grupo
            docs = []
            if group:
                docs = list(group.documents.all())

        # Tabla general
        self.draw_table(table_rows)

        # Tabla de mediciones
        self.section_title('Mediciones registradas')
        if activities_data:
            self._draw_activities_table(activities_data)
        else:
            self._draw_wrapped_paragraph('No se registraron actividades.', width=self.epw)

        # Comentarios / Notas de cierre
        if comments:
            self.section_title('Notas de cierre')
            self._draw_wrapped_paragraph(comments, width=self.epw)

        # Adjuntos (documentos del grupo)
        if not preview_mode and docs:
            self.section_title('Documentos adjuntos')
            for doc in docs:
                # ✅ CORREGIDO: se reemplaza el bullet '•' por un guión simple '-'
                self._draw_wrapped_paragraph(f'- {doc.original_filename}', width=self.epw)

    def _draw_activities_table(self, activities):
        col_widths = [80, 25, 25, 50]  # mm
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(220, 220, 220)
        self.set_draw_color(150, 150, 150)

        x_start = self.l_margin
        y = self.get_y()
        headers = ['Actividad', 'Tiempo', 'Completado', 'Medición']
        for i, header in enumerate(headers):
            self.set_xy(x_start, y)
            self.cell(col_widths[i], 8, normalize(header), 1, 0, 'C', 1)
            x_start += col_widths[i]
        self.ln(8)

        self.set_font('Helvetica', '', 9)
        fill = False
        for act_name, duration, completed, measured in activities:
            x_start = self.l_margin
            y = self.get_y()
            if y + 8 > self.page_break_trigger:
                self.add_page()
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