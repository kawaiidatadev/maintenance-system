from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, BooleanField, DateField
from wtforms.validators import DataRequired, Optional, NumberRange

class AutonomousActivityForm(FlaskForm):
    equipment_id = SelectField('Equipo', coerce=int, validators=[DataRequired()])
    name = StringField('Nombre', validators=[DataRequired()])
    description = TextAreaField('Descripción', validators=[Optional()])
    instructions = TextAreaField('Instrucciones', validators=[Optional()])
    frequency_type = SelectField('Frecuencia', choices=[('daily','Diaria'),('weekly','Semanal'),('monthly','Mensual')])
    frequency_value = IntegerField('Cada', default=1, validators=[NumberRange(min=1)])
    is_active = BooleanField('Activa', default=True)

class RegisterForm(FlaskForm):
    responsible_id = SelectField('Operador', coerce=int, validators=[DataRequired()])
    executed_date = DateField('Fecha de ejecución', validators=[DataRequired()])
    compliance = BooleanField('¿Se cumplió?', default=True)
    comments = TextAreaField('Comentarios / Anomalías')
    create_work_order = BooleanField('Crear OT por anomalía', default=False)