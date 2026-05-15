from app import db
from app.blueprints.minutes.models import Minute, MinuteParticipant, MinuteTask, MinuteComment
from datetime import datetime

def create_minute(title, description, topic, meeting_date, participants_ids, created_by):
    minute = Minute(
        title=title,
        description=description,
        topic=topic,
        meeting_date=meeting_date,
        created_by_id=created_by.id,
        status='open'
    )
    db.session.add(minute)
    db.session.commit()
    # Agregar participantes
    for uid in participants_ids:
        mp = MinuteParticipant(minute_id=minute.id, user_id=uid)
        db.session.add(mp)
    db.session.commit()
    # Opcional: notificar a participantes
    return minute.id

def update_minute(minute, data, participants_ids, current_user):
    minute.title = data.get('title')
    minute.description = data.get('description')
    minute.topic = data.get('topic')
    minute.meeting_date = data.get('meeting_date')
    # Actualizar participantes
    # Eliminar actuales y añadir nuevos
    MinuteParticipant.query.filter_by(minute_id=minute.id).delete()
    for uid in participants_ids:
        mp = MinuteParticipant(minute_id=minute.id, user_id=uid)
        db.session.add(mp)
    db.session.commit()

def add_task(minute, description, assigned_to_id, due_date, current_user):
    task = MinuteTask(
        minute_id=minute.id,
        description=description,
        assigned_to_id=assigned_to_id if assigned_to_id != 0 else None,
        due_date=due_date,
        status='pending'
    )
    db.session.add(task)
    db.session.commit()
    # Opcional: notificar al asignado

def complete_task(task, current_user):
    task.status = 'completed'
    task.completed_at = datetime.utcnow()
    db.session.commit()
    # Opcional: notificar al creador de la tarea

def add_comment(minute, comment_text, user):
    comment = MinuteComment(
        minute_id=minute.id,
        user_id=user.id,
        comment=comment_text
    )
    db.session.add(comment)
    db.session.commit()