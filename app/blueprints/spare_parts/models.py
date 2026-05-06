from app import db
from datetime import datetime


class SparePart(db.Model):
    __tablename__ = 'spare_parts'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    item_type = db.Column(db.Enum('spare', 'consumable'), default='spare')
    brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    supplier = db.Column(db.String(200))
    supplier_part_number = db.Column(db.String(100))
    category = db.Column(db.String(50))
    technical_data = db.Column(db.JSON)
    unit = db.Column(db.String(20), default='pieza')
    criticality = db.Column(db.Enum('low', 'medium', 'high', 'critical'), default='medium')
    purchase_url = db.Column(db.String(500))
    unit_price = db.Column(db.Numeric(12, 2))
    shipping_cost = db.Column(db.Numeric(12, 2))
    currency = db.Column(db.String(3), default='USD')
    estimated_life_hours = db.Column(db.Integer)
    estimated_life_years = db.Column(db.Numeric(5, 2))
    image_path = db.Column(db.String(255))
    barcode = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relaciones (activity_links eliminada)
    stocks = db.relationship('InventoryStock', backref='spare_part', lazy='dynamic')
    movements = db.relationship('SparePartMovement', backref='spare_part', lazy='dynamic')
    equipment_links = db.relationship('EquipmentSparePart', backref='spare_part', lazy='dynamic')

    @property
    def total_unit_cost(self):
        if self.unit_price and self.shipping_cost:
            return self.unit_price + self.shipping_cost
        return self.unit_price or 0

    def __repr__(self):
        return f'<SparePart {self.code}>'


class InventoryStock(db.Model):
    __tablename__ = 'inventory_stocks'
    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    warehouse = db.Column(db.String(50), default='General')
    location_shelf = db.Column(db.String(50))
    minimum_stock = db.Column(db.Integer, default=0)
    maximum_stock = db.Column(db.Integer, default=0)
    reorder_point = db.Column(db.Integer, default=0)
    current_stock = db.Column(db.Integer, default=0)
    last_count_date = db.Column(db.Date)
    __table_args__ = (db.UniqueConstraint('spare_part_id', 'warehouse', name='unique_spare_warehouse'),)


class SparePartMovement(db.Model):
    __tablename__ = 'spare_part_movements'
    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    warehouse = db.Column(db.String(50), default='General')
    movement_type = db.Column(db.Enum('in', 'out'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reference_number = db.Column(db.String(100))
    description = db.Column(db.Text)
    performed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'), nullable=True)
    preventive_execution_log_id = db.Column(db.Integer, db.ForeignKey('preventive_execution_log.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    performed_by = db.relationship('User', foreign_keys=[performed_by_id])
    work_order = db.relationship('WorkOrder', foreign_keys=[work_order_id])
    preventive_log = db.relationship('PreventiveExecutionLog', foreign_keys=[preventive_execution_log_id])


class EquipmentSparePart(db.Model):
    __tablename__ = 'equipment_spare_parts'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    quantity_required = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text)
    equipment = db.relationship('Equipment', backref='spare_parts_links')
    __table_args__ = (db.UniqueConstraint('equipment_id', 'spare_part_id', name='unique_equipment_spare'),)


class ActivitySparePart(db.Model):
    __tablename__ = 'activity_spare_parts'
    id = db.Column(db.Integer, primary_key=True)
    preventive_activity_id = db.Column(db.Integer, db.ForeignKey('preventive_activities.id'))
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'))
    quantity_required = db.Column(db.Integer, default=1)

    # Solo la relación con PreventiveActivity (sin backref conflictivo)
    preventive_activity = db.relationship('PreventiveActivity', back_populates='spare_parts_links')

    # Opcional: propiedad para obtener el objeto SparePart sin relación directa
    @property
    def spare_part(self):
        from app.blueprints.spare_parts.models import SparePart
        return SparePart.query.get(self.spare_part_id)


class StockAlert(db.Model):
    __tablename__ = 'stock_alerts'
    id = db.Column(db.Integer, primary_key=True)
    spare_part_id = db.Column(db.Integer, db.ForeignKey('spare_parts.id'), nullable=False)
    warehouse = db.Column(db.String(50))
    alert_type = db.Column(db.Enum('low_stock', 'reorder', 'expired'), nullable=False)
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    spare_part = db.relationship('SparePart', backref='alerts')
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])