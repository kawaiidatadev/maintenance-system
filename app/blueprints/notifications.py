from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.notification import Notification
from app.models.notification_rule import NotificationRule
from app.models.user_notification_preference import UserNotificationPreference

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


@notifications_bp.route('/')
@login_required
def index():
    # Paginación simple
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    return render_template('notifications/index.html', notifications=notifications)


@notifications_bp.route('/mark_read/<int:id>')
@login_required
def mark_read(id):
    notif = Notification.query.get_or_404(id)
    if notif.user_id != current_user.id:
        flash('No tienes permiso', 'danger')
        return redirect(url_for('notifications.index'))
    notif.mark_as_read()
    return redirect(request.referrer or url_for('notifications.index'))


@notifications_bp.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    if request.method == 'POST':
        rules = NotificationRule.query.filter_by(is_active=True).all()
        for rule in rules:
            pref = UserNotificationPreference.query.filter_by(user_id=current_user.id, rule_id=rule.id).first()
            if not pref:
                pref = UserNotificationPreference(user_id=current_user.id, rule_id=rule.id)
                db.session.add(pref)
            pref.is_enabled = f'rule_{rule.id}_enabled' in request.form
            pref.channel_email = f'rule_{rule.id}_email' in request.form
            custom_priority = request.form.get(f'rule_{rule.id}_priority')
            pref.custom_priority = custom_priority if custom_priority else None
        db.session.commit()
        flash('Preferencias guardadas', 'success')
        return redirect(url_for('notifications.preferences'))

    rules = NotificationRule.query.filter_by(is_active=True).all()
    user_prefs = {}
    for rule in rules:
        pref = UserNotificationPreference.query.filter_by(user_id=current_user.id, rule_id=rule.id).first()
        if not pref:
            pref = UserNotificationPreference(user_id=current_user.id, rule_id=rule.id, is_enabled=True, channel_in_app=True)
            db.session.add(pref)
            db.session.commit()
        user_prefs[rule.id] = pref
    return render_template('notifications/preferences.html', rules=rules, user_prefs=user_prefs)