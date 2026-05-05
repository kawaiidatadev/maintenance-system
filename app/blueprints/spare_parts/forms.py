from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DecimalField, IntegerField, BooleanField, URLField, FloatField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError
from app.blueprints.spare_parts.models import SparePart

class SparePartForm(FlaskForm):
    code = StringField('Código', validators=[DataRequired(), Length(max=50)])
    name = StringField('Nombre', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descripción', validators=[Optional()])
    item_type = SelectField('Tipo', choices=[('spare', 'Refacción'), ('consumable', 'Consumible')], default='spare')
    brand = StringField('Marca', validators=[Optional(), Length(max=100)])
    model = StringField('Modelo', validators=[Optional(), Length(max=100)])
    serial_number = StringField('Número de serie', validators=[Optional(), Length(max=100)])
    supplier = StringField('Proveedor', validators=[Optional(), Length(max=200)])
    supplier_part_number = StringField('Número de pieza del proveedor', validators=[Optional(), Length(max=100)])
    category = StringField('Categoría', validators=[Optional(), Length(max=50)])
    technical_data = TextAreaField('Datos técnicos (JSON)', validators=[Optional()])
    unit = StringField('Unidad', default='pieza', validators=[Optional(), Length(max=20)])
    criticality = SelectField('Criticidad', choices=[('low', 'Baja'), ('medium', 'Media'), ('high', 'Alta'), ('critical', 'Crítica')], default='medium')
    purchase_url = URLField('URL de compra', validators=[Optional(), Length(max=500)])
    unit_price = DecimalField('Precio unitario', places=2, validators=[Optional()])
    shipping_cost = DecimalField('Costo de envío', places=2, default=0, validators=[Optional()])
    currency = StringField('Moneda', default='USD', validators=[Optional(), Length(max=3)])
    estimated_life_hours = IntegerField('Vida útil (horas)', validators=[Optional()])
    estimated_life_years = FloatField('Vida útil (años)', validators=[Optional()])
    image_path = StringField('Ruta de imagen', validators=[Optional(), Length(max=255)])
    barcode = StringField('Código de barras', validators=[Optional(), Length(max=100)])

    def validate_code(self, field):
        if SparePart.query.filter_by(code=field.data).first():
            raise ValidationError('Ya existe una refacción con ese código.')