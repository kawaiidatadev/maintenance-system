from app import db
from datetime import datetime
from sqlalchemy import event


class Equipment(db.Model):
    __tablename__ = 'equipment'

    id = db.Column(db.Integer, primary_key=True)

    # Relación con sistema
    system_id = db.Column(db.Integer, db.ForeignKey('systems.id'))

    # Datos básicos
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    location = db.Column(db.String(100))
    plant_section = db.Column(db.String(50))

    # Atributos técnicos
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    installation_date = db.Column(db.Date)

    # Atributos avanzados (opcionales)
    estimated_life_hours = db.Column(db.Float, nullable=True)
    commissioning_date = db.Column(db.Date)
    recommended_specialty = db.Column(db.String(50))
    life_remaining_hours = db.Column(db.Float, nullable=True)
    last_maintenance_date = db.Column(db.Date)
    total_operating_hours = db.Column(db.Float, default=0)

    # Foto del equipo
    photo_filename = db.Column(db.String(200), nullable=True)

    # Estado y descripción
    status = db.Column(db.String(20), default='Operativo')
    description = db.Column(db.Text)

    # Criticidad
    safety_score = db.Column(db.Integer)
    production_score = db.Column(db.Integer)
    quality_score = db.Column(db.Integer)
    maintenance_score = db.Column(db.Integer)
    criticality = db.Column(db.String(1))
    last_criticality_review = db.Column(db.Date)

    # Datos económicos
    equipment_cost_mxn = db.Column(db.Float, comment='Costo del equipo antes de IVA/impuestos (MXN)')
    downtime_cost_mxn = db.Column(db.Float, comment='Valor de parada por hora (MXN)')
    repair_cost_mxn = db.Column(db.Float, comment='Calculado: 50% del equipment_cost_mxn')
    downtime_cost_level = db.Column(db.String(10))
    repair_cost_level = db.Column(db.String(10))

    # Disponibilidad cualitativa
    availability_level = db.Column(db.String(50))

    # Modelo
    maintenance_model = db.Column(db.String(30))
    model_justification = db.Column(db.Text)

    # Legal y subcontrato
    has_legal_maintenance = db.Column(db.Boolean, default=False)
    legal_requirements = db.Column(db.Text)
    has_subcontracted = db.Column(db.Boolean, default=False)
    subcontract_details = db.Column(db.Text)

    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Nuevos campos (agregar dentro de la clase Equipment)
    operating_time_method = db.Column(db.String(30))  # manual_fixed, counter_reading, etc.
    daily_operating_hours = db.Column(db.Float)
    operating_days_per_week = db.Column(db.Integer)
    initial_counter_value = db.Column(db.Float)
    last_counter_value = db.Column(db.Float)
    last_counter_reading_date = db.Column(db.Date)

    def calculate_operating_hours(self, reference_date=None):
        """Calcula horas totales según el método seleccionado"""
        if self.operating_time_method == 'manual_fixed':
            return self._calculate_manual_fixed(reference_date)
        elif self.operating_time_method == 'counter_reading':
            return self._calculate_counter_reading()
        else:
            return self.total_operating_hours or 0

    def _calculate_manual_fixed(self, reference_date=None):
        """Método: cálculo automático por horario fijo"""
        if not self.commissioning_date:
            return 0
        if not self.daily_operating_hours or not self.operating_days_per_week:
            return 0

        from datetime import date
        end_date = reference_date or date.today()
        start_date = self.commissioning_date

        if end_date < start_date:
            return 0

        delta_days = (end_date - start_date).days
        weeks = delta_days / 7.0
        operating_days = weeks * self.operating_days_per_week
        total_hours = operating_days * self.daily_operating_hours
        return int(round(total_hours))

    def _calculate_counter_reading(self):
        """Método: lectura de contador (último valor - valor inicial)"""
        if self.initial_counter_value is not None and self.last_counter_value is not None:
            return max(0, self.last_counter_value - self.initial_counter_value)
        return self.total_operating_hours or 0

    def update_operating_hours(self):
        """Actualiza el campo total_operating_hours según el método"""
        self.total_operating_hours = self.calculate_operating_hours()

    # ==================== MÉTODOS ====================

    def calculate_criticality(self):
        """Calcula criticidad: la categoría más alta (A > B > C) según puntuaciones 1-5"""

        def score_to_category(score):
            if score >= 4:
                return 'A'
            elif score >= 2:
                return 'B'
            else:
                return 'C'

        categories = []
        if self.safety_score:
            categories.append(score_to_category(self.safety_score))
        if self.production_score:
            categories.append(score_to_category(self.production_score))
        if self.quality_score:
            categories.append(score_to_category(self.quality_score))
        if self.maintenance_score:
            categories.append(score_to_category(self.maintenance_score))

        if 'A' in categories:
            self.criticality = 'A'
        elif 'B' in categories:
            self.criticality = 'B'
        else:
            self.criticality = 'C' if categories else None
        return self.criticality

    def calculate_repair_cost(self):
        """Calcula repair_cost_mxn como 50% del equipment_cost_mxn"""
        if self.equipment_cost_mxn is not None:
            self.repair_cost_mxn = self.equipment_cost_mxn * 0.5
        else:
            self.repair_cost_mxn = None

    @staticmethod
    def get_percentiles():
        """Calcula percentiles 25 y 75 usando SQL nativo (compatible con MySQL 5.x)"""
        from app import db
        from sqlalchemy import text

        # Percentiles para downtime_cost_mxn
        downtime_p25 = None
        downtime_p75 = None
        repair_p25 = None
        repair_p75 = None

        # Método manual para percentiles usando LIMIT y OFFSET
        # 1. Contar cuántos valores no nulos hay
        result = db.session.query(
            db.func.count(Equipment.downtime_cost_mxn)
        ).filter(Equipment.downtime_cost_mxn.isnot(None)).scalar()

        if result and result > 0:
            count = result
            # Percentil 25: posición en el cuartil 1
            pos_25 = int(count * 0.25)
            # Percentil 75: posición en el cuartil 3
            pos_75 = int(count * 0.75)

            # Obtener valor en la posición pos_25
            p25_result = db.session.query(Equipment.downtime_cost_mxn).filter(
                Equipment.downtime_cost_mxn.isnot(None)
            ).order_by(Equipment.downtime_cost_mxn).offset(pos_25).limit(1).first()
            downtime_p25 = p25_result[0] if p25_result else None

            # Obtener valor en la posición pos_75
            p75_result = db.session.query(Equipment.downtime_cost_mxn).filter(
                Equipment.downtime_cost_mxn.isnot(None)
            ).order_by(Equipment.downtime_cost_mxn).offset(pos_75).limit(1).first()
            downtime_p75 = p75_result[0] if p75_result else None

        # Percentiles para repair_cost_mxn
        result2 = db.session.query(
            db.func.count(Equipment.repair_cost_mxn)
        ).filter(Equipment.repair_cost_mxn.isnot(None)).scalar()

        if result2 and result2 > 0:
            count2 = result2
            pos_25 = int(count2 * 0.25)
            pos_75 = int(count2 * 0.75)

            p25_result = db.session.query(Equipment.repair_cost_mxn).filter(
                Equipment.repair_cost_mxn.isnot(None)
            ).order_by(Equipment.repair_cost_mxn).offset(pos_25).limit(1).first()
            repair_p25 = p25_result[0] if p25_result else None

            p75_result = db.session.query(Equipment.repair_cost_mxn).filter(
                Equipment.repair_cost_mxn.isnot(None)
            ).order_by(Equipment.repair_cost_mxn).offset(pos_75).limit(1).first()
            repair_p75 = p75_result[0] if p75_result else None

        return downtime_p25, downtime_p75, repair_p25, repair_p75

    def determine_cost_levels(self):
        """Asigna 'Alto' o 'Bajo' según percentiles globales"""
        p25_downtime, p75_downtime, p25_repair, p75_repair = Equipment.get_percentiles()

        # Para downtime
        if self.downtime_cost_mxn is not None and p75_downtime is not None:
            if self.downtime_cost_mxn >= p75_downtime:
                self.downtime_cost_level = 'Alto'
            elif self.downtime_cost_mxn <= p25_downtime:
                self.downtime_cost_level = 'Bajo'
            else:
                self.downtime_cost_level = 'Bajo'  # intermedio se considera bajo

        # Para repair cost
        if self.repair_cost_mxn is not None and p75_repair is not None:
            if self.repair_cost_mxn >= p75_repair:
                self.repair_cost_level = 'Alto'
            elif self.repair_cost_mxn <= p25_repair:
                self.repair_cost_level = 'Bajo'
            else:
                self.repair_cost_level = 'Bajo'

    def determine_maintenance_model(self):
        """Selecciona modelo según criticidad, disponibilidad, y niveles de coste (lógica anidada Excel)"""
        if not self.criticality:
            return None

        # Mapeo de disponibilidad
        disp = self.availability_level  # 'Mayor a 90%', 'Media', 'Poco uso o baja posibilidad de fallo'

        # Reglas según tu fórmula
        if self.criticality == 'A':  # Crítico
            if disp == 'Mayor a 90%':
                self.maintenance_model = 'alta_disponibilidad'
                self.model_justification = 'Equipo crítico con disponibilidad >90% → Alta Disponibilidad.'
            elif disp == 'Media':
                self.maintenance_model = 'sistematico'
                self.model_justification = 'Equipo crítico con disponibilidad media → Sistemático.'
            else:
                self.maintenance_model = 'condicional'
                self.model_justification = 'Equipo crítico con poco uso o baja probabilidad de fallo → Condicional.'

        elif self.criticality == 'B':  # Importante
            if self.downtime_cost_level == 'Alto':
                # Modelo programado según disponibilidad
                if disp == 'Mayor a 90%':
                    self.maintenance_model = 'alta_disponibilidad'
                    self.model_justification = 'Equipo importante con coste de parada Alto y disponibilidad >90% → Alta Disponibilidad.'
                elif disp == 'Media':
                    self.maintenance_model = 'sistematico'
                    self.model_justification = 'Equipo importante con coste de parada Alto y disponibilidad media → Sistemático.'
                else:
                    self.maintenance_model = 'condicional'
                    self.model_justification = 'Equipo importante con coste de parada Alto y baja disponibilidad requerida → Condicional.'
            else:  # downtime_cost_level == 'Bajo'
                if self.repair_cost_level == 'Alto':
                    if disp == 'Mayor a 90%':
                        self.maintenance_model = 'alta_disponibilidad'
                        self.model_justification = 'Equipo importante con coste de reparación Alto y disponibilidad >90% → Alta Disponibilidad.'
                    elif disp == 'Media':
                        self.maintenance_model = 'sistematico'
                        self.model_justification = 'Equipo importante con coste de reparación Alto y disponibilidad media → Sistemático.'
                    else:
                        self.maintenance_model = 'condicional'
                        self.model_justification = 'Equipo importante con coste de reparación Alto y baja disponibilidad → Condicional.'
                else:  # repair_cost_level == 'Bajo'
                    self.maintenance_model = 'correctivo'
                    self.model_justification = 'Equipo importante con costes de parada y reparación Bajos → Correctivo.'

        else:  # Prescindible
            self.maintenance_model = 'correctivo'
            self.model_justification = 'Equipo prescindible → Correctivo.'

        return self.maintenance_model

    # ==================== MÉTODOS AUXILIARES ====================

    def calculate_life_remaining(self):
        if self.estimated_life_hours and self.total_operating_hours:
            remaining = self.estimated_life_hours - self.total_operating_hours
            self.life_remaining_hours = max(0, remaining)
        else:
            self.life_remaining_hours = None
        return self.life_remaining_hours

    def get_life_percentage(self):
        if self.estimated_life_hours and self.estimated_life_hours > 0:
            consumed = (self.total_operating_hours / self.estimated_life_hours) * 100
            return min(100, consumed)
        return 0

    def get_system_name(self):
        return self.system.name if self.system else 'Sin sistema'

    def get_criticality_label(self):
        labels = {
            'A': '<span class="badge bg-danger">A - Crítico</span>',
            'B': '<span class="badge bg-warning">B - Importante</span>',
            'C': '<span class="badge bg-success">C - Prescindible</span>'
        }
        return labels.get(self.criticality, '<span class="badge bg-secondary">No definido</span>')

    def get_maintenance_model_label(self):
        models = {
            'correctivo': '<span class="badge bg-secondary">Correctivo</span>',
            'condicional': '<span class="badge bg-info">Condicional</span>',
            'sistematico': '<span class="badge bg-primary">Sistemático</span>',
            'alta_disponibilidad': '<span class="badge bg-danger">Alta Disponibilidad</span>'
        }
        return models.get(self.maintenance_model, '<span class="badge bg-secondary">No definido</span>')

    @staticmethod
    def generate_code(category, location, plant_section):
        category_map = {
            'BOMBA': 'BOM', 'MOTOR': 'MOT', 'COMPRESOR': 'COM',
            'VALVULA': 'VAL', 'TANQUE': 'TAN', 'CINTA': 'CIN',
            'VENTILADOR': 'VEN', 'REDUCTOR': 'RED', 'SENSOR': 'SEN',
            'SECADOR': 'SEC', 'FILTRO': 'FIL', 'PISTOLA': 'PIS',
            'TUBERIA': 'TUB', 'SISTEMA': 'SIS'
        }
        cat_code = category_map.get(category.upper(), category.upper()[:3])
        loc_code = location.upper().replace(' ', '')[:4] if location else 'XXXX'
        sec_code = plant_section.upper().replace(' ', '')[:4] if plant_section else 'XXXX'

        from app.models.equipment import Equipment
        prefix = f"{cat_code}-{loc_code}-{sec_code}"
        count = Equipment.query.filter(
            Equipment.code.like(f"{prefix}%")
        ).count()
        sequential = str(count + 1).zfill(3)
        return f"{prefix}-{sequential}"

    def __repr__(self):
        return f'<Equipment {self.code} - {self.name}>'


# ==================== EVENTOS ====================
@event.listens_for(Equipment, 'before_update')
@event.listens_for(Equipment, 'before_insert')
def calculate_life_remaining(mapper, connection, target):
    target.calculate_life_remaining()
    target.calculate_repair_cost()

