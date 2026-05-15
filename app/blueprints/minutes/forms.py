from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateTimeField, IntegerField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Optional
from app.models.user import User

class MinuteForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descripción', validators=[Optional()])
    topic = StringField('Tema / Equipo', validators=[Length(max=100)])
    meeting_date = DateTimeField('Fecha de reunión', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    participants = SelectMultipleField('Participantes', coerce=int, validators=[Optional()])
    # No incluimos el creador, se asigna desde la sesión

    def __init__(self, *args, **kwargs):
        super(MinuteForm, self).__init__(*args, **kwargs)
        self.participants.choices = [(u.id, u.username) for u in User.query.order_by(User.username).all()]

class TaskForm(FlaskForm):
    description = TextAreaField('Descripción', validators=[DataRequired()])
    assigned_to_id = SelectField('Asignar a', coerce=int, validators=[Optional()])
    due_date = DateTimeField('Fecha límite', format='%Y-%m-%dT%H:%M', validators=[Optional()])

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        self.assigned_to_id.choices = [(0, '-- No asignado --')] + [(u.id, u.username) for u in User.query.order_by(User.username).all()]