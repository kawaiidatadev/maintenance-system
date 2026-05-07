from app import db
from datetime import datetime


class FrequencyGroup(db.Model):
    __tablename__ = 'frequency_groups'

    id = db.Column(db.Integer, primary_key=True)
    # equipment_id ya no es obligatorio; se usa la relación muchos a muchos
    # Relación muchos a muchos
    equipments = db.relationship('Equipment', secondary=db.Table('frequency_group_equipments',
                                                                 db.Column('group_id', db.Integer,
                                                                           db.ForeignKey('frequency_groups.id'),
                                                                           primary_key=True),
                                                                 db.Column('equipment_id', db.Integer,
                                                                           db.ForeignKey('equipment.id'),
                                                                           primary_key=True)
                                                                 ), backref='frequency_groups')
    # El resto de columnas permanecen igual
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    freq_type = db.Column(db.String(20), nullable=False)
    freq_value = db.Column(db.Integer, nullable=False)
    tolerance_days = db.Column(db.Integer, default=2)
    responsible_role = db.Column(db.String(20), nullable=False)
    requires_shutdown = db.Column(db.Boolean, default=False)
    is_legal_requirement = db.Column(db.Boolean, default=False)
    legal_reference = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])

    documents = db.relationship('GroupDocument', backref='group', lazy='dynamic', cascade='all, delete-orphan')

    # ==============================================
    # PROPIEDADES PARA TRADUCCIÓN AL ESPAÑOL
    # ==============================================
    @property
    def frequency_suggested(self):
        """Devuelve la frecuencia formateada en español"""
        if not self.freq_value or not self.freq_type:
            return "No especificada"

        # Traducción del tipo de frecuencia
        freq_type_es = {
            'days': 'días',
            'weeks': 'semanas',
            'months': 'meses',
            'years': 'años'
        }.get(self.freq_type, self.freq_type)

        # Manejar singular (cuando el valor es 1)
        if self.freq_value == 1:
            if freq_type_es == 'días':
                freq_type_es = 'día'
            elif freq_type_es == 'semanas':
                freq_type_es = 'semana'
            elif freq_type_es == 'meses':
                freq_type_es = 'mes'
            elif freq_type_es == 'años':
                freq_type_es = 'año'

        return f"Cada {self.freq_value} {freq_type_es}"

    @property
    def responsible_role_es(self):
        """Devuelve el rol responsable traducido al español"""
        roles = {
            'specialized': 'Especializado',
            'external': 'Externo'
        }
        return roles.get(self.responsible_role, self.responsible_role)

    def __repr__(self):
        return f'<FrequencyGroup {self.name}>'