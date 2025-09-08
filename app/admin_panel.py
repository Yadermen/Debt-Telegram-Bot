from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from wtforms.fields import SelectField

from app.config import SYNC_DATABASE_URL
from app.database.models import Base, User, Debt, ScheduledMessage

db = SQLAlchemy()

# Кастомный ModelView для Debt
class DebtAdmin(ModelView):
    # Явно указываем, что в форме будет user_id, а не relationship user
    form_columns = (
        'user_id', 'person', 'amount', 'currency', 'direction',
        'date', 'due', 'comment', 'closed', 'is_active'
    )
    form_overrides = {'user_id': SelectField}

    def create_form(self, obj=None):
        form = super().create_form(obj)
        form.user_id.choices = [(u.user_id, str(u.user_id)) for u in User.query.all()]
        return form

    def edit_form(self, obj=None):
        form = super().edit_form(obj)
        form.user_id.choices = [(u.user_id, str(u.user_id)) for u in User.query.all()]
        return form


# Кастомный ModelView для ScheduledMessage
class ScheduledMessageAdmin(ModelView):
    form_columns = (
        'user_id', 'text', 'photo_id', 'schedule_time',
        'sent', 'is_active'
    )
    form_overrides = {'user_id': SelectField}

    def create_form(self, obj=None):
        form = super().create_form(obj)
        form.user_id.choices = [(u.user_id, str(u.user_id)) for u in User.query.all()]
        return form

    def edit_form(self, obj=None):
        form = super().edit_form(obj)
        form.user_id.choices = [(u.user_id, str(u.user_id)) for u in User.query.all()]
        return form


def create_admin_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'supersecretkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = SYNC_DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    Base.query = db.session.query_property()

    admin = Admin(app, name='DebtBot Admin', template_mode='bootstrap4')
    admin.add_view(ModelView(User, db.session))
    admin.add_view(DebtAdmin(Debt, db.session))
    admin.add_view(ScheduledMessageAdmin(ScheduledMessage, db.session))

    # Редирект с / на /admin
    @app.route("/")
    def index():
        return redirect(url_for("admin.index"))

    with app.app_context():
        Base.metadata.create_all(bind=db.engine)

    return app
