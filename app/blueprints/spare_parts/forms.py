from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DecimalField, IntegerField, URLField, FloatField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from app.blueprints.spare_parts.models import SparePart

class SparePartForm(FlaskForm):
    id = HiddenField('ID')  # Para edición, evitar validación duplicada

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
    criticality = SelectField('Criticidad',
                              choices=[('low', 'Baja'), ('medium', 'Media'), ('high', 'Alta'), ('critical', 'Crítica')],
                              default='medium')
    purchase_url = URLField('URL de compra', validators=[Optional(), Length(max=500)])
    unit_price = DecimalField('Precio unitario', places=2, validators=[Optional()])
    shipping_cost = DecimalField('Costo de envío', places=2, default=0, validators=[Optional()])
    currency = StringField('Moneda', default='USD', validators=[Optional(), Length(max=3)])
    estimated_life_hours = IntegerField('Vida útil (horas)', validators=[Optional()])
    estimated_life_years = FloatField('Vida útil (años)', validators=[Optional()])

    # Imagen
    image = FileField('Imagen', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Solo se permiten imágenes (jpg, jpeg, png, gif)')
    ])

    # Código de barras (texto)
    barcode = StringField('Código de barras', validators=[Optional(), Length(max=100)])

    # Parámetros de inventario (se guardan en InventoryStock)
    minimum_stock = IntegerField('Stock mínimo', validators=[Optional()], default=0)
    maximum_stock = IntegerField('Stock máximo', validators=[Optional()], default=0)
    reorder_point = IntegerField('Punto de pedido', validators=[Optional()], default=0)
    location_shelf = StringField('Ubicación (estante)', validators=[Optional(), Length(max=50)])

    def validate_code(self, field):
        # Si estamos editando, excluir el registro actual
        if self.id.data:
            existing = SparePart.query.filter(
                SparePart.code == field.data,
                SparePart.id != int(self.id.data)
            ).first()
        else:
            existing = SparePart.query.filter_by(code=field.data).first()
        if existing:
            raise ValidationError('Ya existe una refacción con ese código.')