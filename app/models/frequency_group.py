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
    def __repr__(self):
        return f'<FrequencyGroup {self.name}>'
