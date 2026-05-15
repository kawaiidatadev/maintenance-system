from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.blueprints.autonomous import autonomous_bp
from app.blueprints.autonomous.models import AutonomousActivity, AutonomousExecution
from app.blueprints.autonomous.forms import AutonomousActivityForm, RegisterForm
from app.blueprints.autonomous.services import get_pending_activities
from app.models.equipment import Equipment
from app.models.user import User
from app.models.work_order import WorkOrder

@autonomous_bp.route('/activities')
@login_required
def activities():
    acts = AutonomousActivity.query.filter_by(is_active=True).all()
    return render_template('autonomous/activities.html', activities=acts)

@autonomous_bp.route('/activity/create', methods=['GET', 'POST'])
@login_required
def activity_create():
    form = AutonomousActivityForm()
    form.equipment_id.choices = [(e.id, f"{e.code} - {e.name}") for e in Equipment.query.order_by(Equipment.code).all()]
    if form.validate_on_submit():
        act = AutonomousActivity(
            equipment_id=form.equipment_id.data,
            name=form.name.data,
            description=form.description.data,
            instructions=form.instructions.data,
            frequency_type=form.frequency_type.data,
            frequency_value=form.frequency_value.data,
            is_active=form.is_active.data
        )
        db.session.add(act)
        db.session.commit()
        flash('Actividad autónoma creada', 'success')
        return redirect(url_for('autonomous.activities'))
    return render_template('autonomous/activity_form.html', form=form, title='Nueva actividad autónoma')

@autonomous_bp.route('/activity/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def activity_edit(id):
    act = AutonomousActivity.query.get_or_404(id)
    form = AutonomousActivityForm(obj=act)
    form.equipment_id.choices = [(e.id, f"{e.code} - {e.name}") for e in Equipment.query.order_by(Equipment.code).all()]
    if form.validate_on_submit():
        act.equipment_id = form.equipment_id.data
        act.name = form.name.data
        act.description = form.description.data
        act.instructions = form.instructions.data
        act.frequency_type = form.frequency_type.data
        act.frequency_value = form.frequency_value.data
        act.is_active = form.is_active.data
        db.session.commit()
        flash('Actividad actualizada', 'success')
        return redirect(url_for('autonomous.activities'))
    return render_template('autonomous/activity_form.html', form=form, title='Editar actividad autónoma')

@autonomous_bp.route('/activity/delete/<int:id>', methods=['POST'])
@login_required
def activity_delete(id):
    act = AutonomousActivity.query.get_or_404(id)
    act.is_active = False
    db.session.commit()
    flash('Actividad desactivada', 'success')
    return redirect(url_for('autonomous.activities'))

@autonomous_bp.route('/pending')
@login_required
def pending():
    pending_list = get_pending_activities()
    return render_template('autonomous/pending.html', pending=pending_list)

@autonomous_bp.route('/register/<int:activity_id>', methods=['GET', 'POST'])
@login_required
def register(activity_id):
    activity = AutonomousActivity.query.get_or_404(activity_id)
    form = RegisterForm()
    # Solo mostrar operadores (técnicos) como responsables
    form.responsible_id.choices = [(u.id, u.username) for u in User.query.filter(User.role == 'tecnico').all()]
    if form.validate_on_submit():
        exec_date = form.executed_date.data
        compliance = form.compliance.data
        comments = form.comments.data
        responsible_id = form.responsible_id.data

        wo_id = None
        if form.create_work_order.data and not compliance:
            # Crear OT correctiva
            wo = WorkOrder(
                number=WorkOrder.generate_number(),
                equipment_id=activity.equipment_id,
                problem_description=f"Anomalía en actividad autónoma '{activity.name}': {comments}",
                created_by_id=current_user.id,
                status='open',
                work_type='corrective'
            )
            db.session.add(wo)
            db.session.commit()
            wo_id = wo.id
            flash('Se ha creado una OT correctiva por la anomalía', 'info')

        execution = AutonomousExecution(
            activity_id=activity.id,
            executed_date=exec_date,
            responsible_id=responsible_id,
            verified_by_id=current_user.id,
            compliance=compliance,
            comments=comments,
            work_order_id=wo_id
        )
        db.session.add(execution)
        db.session.commit()
        flash(f'Registro de cumplimiento guardado para {activity.name}', 'success')
        return redirect(url_for('autonomous.pending'))
    return render_template('autonomous/register.html', form=form, activity=activity)

@autonomous_bp.route('/history')
@login_required
def history():
    executions = AutonomousExecution.query.order_by(AutonomousExecution.executed_date.desc()).all()
    return render_template('autonomous/history.html', executions=executions)