from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.blueprints.minutes.models import Minute, MinuteParticipant, MinuteTask, MinuteComment
from app.blueprints.minutes.forms import MinuteForm, TaskForm
from app.blueprints.minutes.services import create_minute, update_minute, add_task, complete_task, add_comment
from functools import wraps
from . import minutes_bp


def admin_or_creator_required(f):
    """Decorador que permite acceso solo a admin o al creador de la minuta"""

    @wraps(f)
    def decorated_function(minute_id, *args, **kwargs):
        minute = Minute.query.get_or_404(minute_id)
        if not (current_user.role == 'admin' or minute.created_by_id == current_user.id):
            flash('No tienes permiso para realizar esta acción.', 'danger')
            return redirect(url_for('minutes.view_minute', minute_id=minute_id))
        return f(minute, *args, **kwargs)

    return decorated_function


# Listado de minutas
@minutes_bp.route('/')
@login_required
def list_minutes():
    print("🔵 DEBUG: Entrando a list_minutes")
    status = request.args.get('status', '')
    topic = request.args.get('topic', '')
    user_id = request.args.get('user', type=int)

    # Cargar minutas con eager loading de participantes y tareas
    query = Minute.query.options(
        db.joinedload(Minute.participants).joinedload(MinuteParticipant.user),
        db.joinedload(Minute.tasks)
    )

    if status:
        query = query.filter(Minute.status == status)
    if topic:
        query = query.filter(Minute.topic.ilike(f'%{topic}%'))
    if user_id:
        query = query.filter(db.or_(
            Minute.created_by_id == user_id,
            Minute.participants.any(user_id=user_id)
        ))
    minutes = query.order_by(Minute.created_at.desc()).all()
    print(f"🔵 DEBUG: {len(minutes)} minutas encontradas")

    # ============================================
    # PRECALCULAR DATOS PARA EL TEMPLATE (SOLUCIÓN DEFINITIVA)
    # ============================================
    for m in minutes:
        # Precalcular participantes
        m.participant_count = len(m.participants)
        m.participant_names = ', '.join([p.user.username for p in m.participants])
        # Precalcular tareas pendientes
        m.pending_tasks_count = len([t for t in m.tasks if t.status == 'pending'])

        # Debug (opcional, para verificar en consola)
        print(f"Minuta {m.id}: {m.participant_count} participantes, {m.pending_tasks_count} tareas pendientes")
        for p in m.participants:
            print(f"  - Participante: {p.user.username}")
        for t in m.tasks:
            print(f"  - Tarea: {t.description} ({t.status})")

    return render_template('minutes/list.html', minutes=minutes, status=status, topic=topic)


# ============================================
# VISTAS FILTRADAS PARA MINUTAS
# ============================================

@minutes_bp.route('/my')
@login_required
def my_minutes():
    """Minutas donde el usuario actual es creador o participante"""
    minutes = Minute.query.filter(
        db.or_(
            Minute.created_by_id == current_user.id,
            Minute.participants.any(user_id=current_user.id)
        )
    ).order_by(Minute.created_at.desc()).all()

    # Precalcular datos
    for m in minutes:
        m.participant_count = len(m.participants)
        m.participant_names = ', '.join([p.user.username for p in m.participants])
        m.pending_tasks_count = sum(1 for t in m.tasks if t.status == 'pending')

    return render_template('minutes/list.html', minutes=minutes, title='Mis minutas')


@minutes_bp.route('/pending')
@login_required
def pending_minutes():
    """Tareas pendientes asignadas al usuario actual"""
    from datetime import datetime
    tasks = MinuteTask.query.filter(
        MinuteTask.status == 'pending',
        MinuteTask.assigned_to_id == current_user.id
    ).order_by(MinuteTask.due_date.asc()).all()

    return render_template('minutes/pending_tasks.html', tasks=tasks, now=datetime.utcnow())
@minutes_bp.route('/participants')
@login_required
def my_participations():
    """Minutas donde el usuario actual es solo participante (no creador)"""
    minutes = Minute.query.filter(
        Minute.participants.any(user_id=current_user.id),
        Minute.created_by_id != current_user.id
    ).order_by(Minute.created_at.desc()).all()

    for m in minutes:
        m.participant_count = len(m.participants)
        m.participant_names = ', '.join([p.user.username for p in m.participants])
        m.pending_tasks_count = sum(1 for t in m.tasks if t.status == 'pending')

    return render_template('minutes/list.html', minutes=minutes, title='Participante')


# ============================================

# Crear minuta
@minutes_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = MinuteForm()
    if form.validate_on_submit():
        minute_id = create_minute(
            title=form.title.data,
            description=form.description.data,
            topic=form.topic.data,
            meeting_date=form.meeting_date.data,
            participants_ids=form.participants.data,
            created_by=current_user
        )
        flash('Minuta creada exitosamente.', 'success')
        return redirect(url_for('minutes.view_minute', minute_id=minute_id))
    return render_template('minutes/create.html', form=form)


# Ver detalle
@minutes_bp.route('/<int:minute_id>')
@login_required
def view_minute(minute_id):
    minute = Minute.query.get_or_404(minute_id)
    # Verificar si el usuario puede ver (participante, creador o admin)
    if not (current_user.role == 'admin' or minute.created_by_id == current_user.id or
            any(p.user_id == current_user.id for p in minute.participants)):
        flash('No tienes permiso para ver esta minuta.', 'danger')
        return redirect(url_for('minutes.list_minutes'))
    task_form = TaskForm()
    return render_template('minutes/view.html', minute=minute, task_form=task_form)


# Editar minuta
@minutes_bp.route('/<int:minute_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_or_creator_required
def edit_minute(minute, minute_id=None):
    form = MinuteForm(obj=minute)
    if request.method == 'GET':
        form.participants.data = [p.user_id for p in minute.participants]
    if form.validate_on_submit():
        update_minute(minute, form.data, form.participants.data, current_user)
        flash('Minuta actualizada.', 'success')
        return redirect(url_for('minutes.view_minute', minute_id=minute.id))
    return render_template('minutes/edit.html', form=form, minute=minute)


# Agregar tarea
@minutes_bp.route('/<int:minute_id>/add_task', methods=['POST'])
@login_required
def add_task_view(minute_id):
    minute = Minute.query.get_or_404(minute_id)
    if not (current_user.role == 'admin' or minute.created_by_id == current_user.id):
        flash('No autorizado.', 'danger')
        return redirect(url_for('minutes.view_minute', minute_id=minute_id))
    form = TaskForm()
    if form.validate_on_submit():
        add_task(minute, form.description.data, form.assigned_to_id.data, form.due_date.data, current_user)
        flash('Tarea agregada.', 'success')
    else:
        flash('Error en el formulario.', 'danger')
    return redirect(url_for('minutes.view_minute', minute_id=minute_id))


# Completar tarea
@minutes_bp.route('/task/<int:task_id>/complete', methods=['POST'])
@login_required
def complete_task_view(task_id):
    task = MinuteTask.query.get_or_404(task_id)
    minute = task.minute
    if not (
            current_user.role == 'admin' or minute.created_by_id == current_user.id or task.assigned_to_id == current_user.id):
        flash('No autorizado.', 'danger')
        return redirect(url_for('minutes.view_minute', minute_id=minute.id))
    complete_task(task, current_user)
    flash('Tarea marcada como completada.', 'success')
    return redirect(url_for('minutes.view_minute', minute_id=minute.id))


# Agregar comentario
@minutes_bp.route('/<int:minute_id>/add_comment', methods=['POST'])
@login_required
def add_comment_view(minute_id):
    minute = Minute.query.get_or_404(minute_id)
    comment_text = request.form.get('comment')
    if comment_text:
        add_comment(minute, comment_text, current_user)
        flash('Comentario agregado.', 'success')
    else:
        flash('El comentario no puede estar vacío.', 'danger')
    return redirect(url_for('minutes.view_minute', minute_id=minute_id))

