from app import db
from datetime import datetime


class PreventiveSchedule(db.Model):
    __tablename__ = 'preventive_schedules'

    id = db.Column(db.Integer, primary_key=True)

    # Relación con grupo (NUEVO, principal)
    group_id = db.Column(db.Integer, db.ForeignKey('frequency_groups.id'), nullable=True)
    group = db.relationship('FrequencyGroup', backref='schedules')

    # Relación con actividad individual (legacy, puede ser null)
    activity_id = db.Column(db.Integer, db.ForeignKey('preventive_activities.id'), nullable=True)
    activity = db.relationship('PreventiveActivity')

    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    equipment = db.relationship('Equipment')

    # Fechas clave
    last_completion_date = db.Column(db.DateTime)
    last_completion_notes = db.Column(db.Text)  # ← agregar este campo
    next_due_date = db.Column(db.DateTime)

    # Para mantenimiento basado en horas (opcional)
    last_counter_value = db.Column(db.Float, default=0)
    next_due_hours = db.Column(db.Float)

    # Reprogramación
    is_postponed = db.Column(db.Boolean, default=False)
    postpone_reason = db.Column(db.Text)
    postponed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    postponed_by = db.relationship('User')

    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def compute_next_due(self, real_execution_date=None):
        """
        Calcula la próxima fecha según la frecuencia del grupo (si existe) o de la actividad.
        """
        from dateutil.relativedelta import relativedelta
        from datetime import timedelta

        base_date = real_execution_date if real_execution_date else self.last_completion_date
        if not base_date:
            return None

        # Prioridad: si hay grupo, usar su frecuencia
        if self.group_id and self.group:
            freq_type = self.group.freq_type
            freq_value = self.group.freq_value
        elif self.activity_id and self.activity:
            freq_type = self.activity.freq_type
            freq_value = self.activity.freq_value
        else:
            return None

        if freq_type == 'days':
            return base_date + timedelta(days=freq_value)
        elif freq_type == 'weeks':
            return base_date + timedelta(weeks=freq_value)
        elif freq_type == 'months':
            return base_date + relativedelta(months=freq_value)
        elif freq_type == 'years':
            return base_date + relativedelta(years=freq_value)
        return None