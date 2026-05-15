from app import db
from datetime import datetime

class Minute(db.Model):
    __tablename__ = 'minutes'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    topic = db.Column(db.String(100))          # tema/equipo
    meeting_date = db.Column(db.DateTime)      # fecha de la reunión
    status = db.Column(db.String(20), default='open')  # open, closed
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relaciones
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    participants = db.relationship('MinuteParticipant', back_populates='minute', cascade='all, delete-orphan')
    tasks = db.relationship('MinuteTask', back_populates='minute', cascade='all, delete-orphan')
    comments = db.relationship('MinuteComment', back_populates='minute', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Minute {self.title}>'


class MinuteParticipant(db.Model):
    __tablename__ = 'minute_participants'

    id = db.Column(db.Integer, primary_key=True)
    minute_id = db.Column(db.Integer, db.ForeignKey('minutes.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    minute = db.relationship('Minute', back_populates='participants')
    user = db.relationship('User', backref='minute_participations')

    __table_args__ = (db.UniqueConstraint('minute_id', 'user_id', name='unique_minute_user'),)


class MinuteTask(db.Model):
    __tablename__ = 'minute_tasks'

    id = db.Column(db.Integer, primary_key=True)
    minute_id = db.Column(db.Integer, db.ForeignKey('minutes.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)  # notas adicionales

    # Relaciones
    minute = db.relationship('Minute', back_populates='tasks')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])

    def __repr__(self):
        return f'<MinuteTask {self.description[:30]}>'


class MinuteComment(db.Model):
    __tablename__ = 'minute_comments'

    id = db.Column(db.Integer, primary_key=True)
    minute_id = db.Column(db.Integer, db.ForeignKey('minutes.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    minute = db.relationship('Minute', back_populates='comments')
    user = db.relationship('User', backref='minute_comments')