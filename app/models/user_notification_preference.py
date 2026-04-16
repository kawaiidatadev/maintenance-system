from app import db

class UserNotificationPreference(db.Model):
    __tablename__ = 'user_notification_preferences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id])
    rule_id = db.Column(db.Integer, db.ForeignKey('notification_rules.id'), nullable=False)
    rule = db.relationship('NotificationRule', foreign_keys=[rule_id])
    is_enabled = db.Column(db.Boolean, default=True)
    channel_in_app = db.Column(db.Boolean, default=True)
    channel_email = db.Column(db.Boolean, default=False)
    # No hay custom_priority

    def __repr__(self):
        return f'<UserPref {self.user_id} rule={self.rule_id}>'