import os
from flask import Flask, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    current_user, login_required
)
from wtforms.fields import SelectField
from wtforms.validators import DataRequired
from dotenv import load_dotenv

from app.config import SYNC_DATABASE_URL
from app.database.models import Base, User, Debt, ScheduledMessage

# Загружаем переменные окружения
load_dotenv()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

db = SQLAlchemy()
login_manager = LoginManager()

# Фейковый пользователь для Flask-Login
class AdminUser(UserMixin):
    id = 1  # фиксированный ID

@login_manager.user_loader
def load_user(user_id):
    if user_id == "1":
        return AdminUser()
    return None

# Кастомная главная страница админки с защитой
class SecureAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

# Базовый класс с защитой для всех ModelView
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

# Миксин для выбора user_id
class UserIdSelectMixin:
    form_overrides = {'user_id': SelectField}
    form_args = {
        'user_id': {
            'validators': [DataRequired(message="Выберите пользователя")]
        }
    }
    def _set_user_choices(self, form):
        users = User.query.all()
        form.user_id.choices = [(u.user_id, str(u.user_id)) for u in users]
        if not users:
            flash("⚠️ Нет пользователей в базе. Сначала создайте пользователя.", "warning")
        else:
            form.user_id.default = users[0].user_id
        return form
    def create_form(self, obj=None):
        return self._set_user_choices(super().create_form(obj))
    def edit_form(self, obj=None):
        return self._set_user_choices(super().edit_form(obj))

class DebtAdmin(UserIdSelectMixin, SecureModelView):
    form_columns = ('user_id', 'person', 'amount', 'currency', 'direction',
                    'date', 'due', 'comment', 'closed', 'is_active')

class ScheduledMessageAdmin(UserIdSelectMixin, SecureModelView):
    form_columns = ('user_id', 'text', 'photo_id', 'schedule_time',
                    'sent', 'is_active')

class UserAdmin(SecureModelView):
    def delete_model(self, model):
        for debt in list(model.debts):
            db.session.delete(debt)
        for msg in list(model.scheduled_messages):
            db.session.delete(msg)
        db.session.delete(model)
        db.session.commit()
        flash(f"Пользователь {model.user_id} и все связанные записи удалены", "success")
        return True

def create_admin_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'supersecretkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = SYNC_DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    Base.query = db.session.query_property()

    admin = Admin(
        app,
        name='DebtBot Admin',
        template_mode='bootstrap4',
        index_view=SecureAdminIndexView()
    )
    admin.add_view(UserAdmin(User, db.session))
    admin.add_view(DebtAdmin(Debt, db.session))
    admin.add_view(ScheduledMessageAdmin(ScheduledMessage, db.session))

    @app.route("/")
    def index():
        return redirect(url_for("admin.index"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                login_user(AdminUser())
                next_url = request.args.get("next") or url_for("admin.index")
                return redirect(next_url)
            flash("Неверный логин или пароль", "danger")
        return '''
            <h2>Вход в админку</h2>
            <form method="post">
                <input type="text" name="username" placeholder="Логин" required>
                <input type="password" name="password" placeholder="Пароль" required>
                <input type="submit" value="Войти">
            </form>
        '''

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    with app.app_context():
        Base.metadata.create_all(bind=db.engine)

    return app
