import os
from flask import Flask, redirect, url_for, flash, request, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView, expose, BaseView
from flask_admin.contrib.sqla import ModelView
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    current_user, login_required
)
from wtforms.fields import SelectField, StringField
from wtforms.validators import DataRequired
from dotenv import load_dotenv
from markupsafe import Markup
from sqlalchemy import func, case

from app.config import SYNC_DATABASE_URL
from app.database.models import Base, User, Debt, ScheduledMessage, Reminder

# Загружаем переменные окружения
load_dotenv()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

db = SQLAlchemy()
login_manager = LoginManager()

# Словарь для перевода направлений
DIRECTION_TRANSLATIONS = {
    'ru': {
        'owe': 'Я должен',
        'owed': 'Мне должны'
    },
    'uz': {
        'owe': 'Men qarzman',
        'owed': 'Menga qarz'
    },
    'en': {
        'owe': 'I owe',
        'owed': 'Owes me'
    }
}


# Фейковый пользователь для Flask-Login
class AdminUser(UserMixin):
    id = 1


@login_manager.user_loader
def load_user(user_id):
    if user_id == "1":
        return AdminUser()
    return None


# Кастомная главная страница со статистикой
class SecureAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

    @expose('/')
    def index(self):
        # Получаем статистику по всем пользователям
        users_stats = []
        users = User.query.all()
        direction_map = {
            'owe': 'owe',
            'owed': 'owed',
            'gave': 'owe',  # трактуем как "я отдал" → я должен
            'took': 'owed'  # трактуем как "я взял" → мне должны
        }

        for user in users:
            # Подсчитываем долги по валютам
            stats_by_currency = db.session.query(
                Debt.currency,
                Debt.direction,
                func.sum(Debt.amount).label('total')
            ).filter(
                Debt.user_id == user.user_id,
                Debt.is_active == True,
                Debt.closed == False
            ).group_by(Debt.currency, Debt.direction).all()

            # Группируем по валютам
            currency_stats = {}
            for currency, direction, total in stats_by_currency:
                norm_dir = direction_map.get(direction, direction)  # нормализация
                if currency not in currency_stats:
                    currency_stats[currency] = {'owe': 0, 'owed': 0}
                currency_stats[currency][norm_dir] = float(total or 0)

            # Считаем баланс
            balance_by_currency = {}
            for currency, amounts in currency_stats.items():
                balance = amounts['owed'] - amounts['owe']
                balance_by_currency[currency] = balance

            users_stats.append({
                'user': user,
                'currency_stats': currency_stats,
                'balance': balance_by_currency,
                'total_debts': len([d for d in user.debts if d.is_active and not d.closed])
            })

        total_users = len(users)
        total_debts = Debt.query.filter_by(is_active=True, closed=False).count()
        total_scheduled = ScheduledMessage.query.filter_by(is_active=True, sent=False).count()
        total_reminders = Reminder.query.filter_by(is_active=True).count()

        return self.render('admin/custom_index.html',
                           users_stats=users_stats,
                           total_users=total_users,
                           total_debts=total_debts,
                           total_scheduled=total_scheduled,
                           total_reminders=total_reminders)


# Базовый класс с защитой для всех ModelView
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))


# Миксин для выбора user_id с автоопределением языка
class UserIdSelectMixin:
    form_overrides = {'user_id': SelectField}
    form_args = {
        'user_id': {
            'validators': [DataRequired(message="Выберите пользователя")]
        }
    }

    def _set_user_choices(self, form):
        users = User.query.all()
        form.user_id.choices = [(u.user_id, f"{u.user_id} - {u.lang or 'не указан'}") for u in users]
        if not users:
            flash("⚠️ Нет пользователей в базе. Сначала создайте пользователя.", "warning")
        else:
            form.user_id.default = users[0].user_id
        return form

    def create_form(self, obj=None):
        return self._set_user_choices(super().create_form(obj))

    def edit_form(self, obj=None):
        return self._set_user_choices(super().edit_form(obj))


class UserAdmin(SecureModelView):
    can_view_details = True
    column_list = ('user_id', 'lang', 'notify_time', 'currency_notify_time', 'is_active', 'created_at')
    column_searchable_list = ['user_id']
    column_filters = ['lang', 'is_active']
    column_labels = {
        'user_id': 'ID пользователя',
        'lang': 'Язык',
        'notify_time': 'Время уведомлений',
        'currency_notify_time': 'Время валютных уведомлений',
        'is_active': 'Активен',
        'created_at': 'Создан'
    }

    # Форматтер для ссылок на долги
    def _debt_link_formatter(view, context, model, name):
        count = len([d for d in model.debts if d.is_active and not d.closed])
        if count > 0:
            url = url_for('user_stats.details', user_id=model.user_id)
            return Markup(f'<a class="btn btn-primary btn-sm" href="{url}">Посмотреть долги ({count})</a>')
        return '0 долгов'

    # Форматтер для ссылок на сообщения
    def _message_link_formatter(view, context, model, name):
        count = len([m for m in model.scheduled_messages if m.is_active and not m.sent])
        if count > 0:
            url = url_for('scheduledmessage.index_view', flt0_0=model.user_id)
            return Markup(f'<a href="{url}">{count} сообщений</a>')
        return '0 сообщений'

    column_formatters = {
        'debts': _debt_link_formatter,
        'scheduled_messages': _message_link_formatter
    }

    column_extra_row_actions = None

    # 🔑 Переопределяем details_view, чтобы глазик вел на статистику
    @expose('/details/')
    def details_view(self):
        user_id = request.args.get('id')
        if not user_id:
            flash("❌ Не указан ID пользователя", "error")
            return redirect(url_for('.index_view'))
        return redirect(url_for('user_stats.details', user_id=user_id))

    def delete_model(self, model):
        user_id = model.user_id
        # Удаляем связанные записи
        for debt in list(model.debts):
            db.session.delete(debt)
        for msg in list(model.scheduled_messages):
            db.session.delete(msg)
        # Удаляем напоминания если есть
        Reminder.query.filter_by(user_id=user_id).delete()
        db.session.delete(model)
        db.session.commit()
        flash(f"✅ Пользователь {user_id} и все связанные записи удалены", "success")
        return True


class DebtAdmin(UserIdSelectMixin, SecureModelView):
    can_view_details = True
    column_list = ('id', 'user_id', 'person', 'amount', 'currency',
                   'direction', 'date', 'due', 'closed', 'is_active')
    column_searchable_list = ['person', 'comment']
    column_filters = ['user_id', 'currency', 'direction', 'closed', 'is_active']
    column_default_sort = ('date', True)
    column_labels = {
        'id': 'ID',
        'user_id': 'Пользователь',
        'person': 'Кому/От кого',
        'amount': 'Сумма',
        'currency': 'Валюта',
        'direction': 'Направление',
        'date': 'Дата',
        'due': 'Срок',
        'comment': 'Комментарий',
        'closed': 'Закрыт',
        'is_active': 'Активен'
    }

    form_columns = ('user_id', 'person', 'amount', 'currency', 'direction',
                    'date', 'due', 'comment', 'closed', 'is_active')

    # Автоматический перевод направления при создании
    def on_model_change(self, form, model, is_created):
        if is_created:
            # Получаем пользователя
            user = User.query.filter_by(user_id=model.user_id).first()
            if user and user.lang:
                lang = user.lang.lower()
                # Если направление на английском, переводим
                if model.direction in ['owe', 'owed']:
                    if lang in DIRECTION_TRANSLATIONS:
                        translated = DIRECTION_TRANSLATIONS[lang].get(model.direction)
                        if translated:
                            flash(f"ℹ️ Направление автоматически переведено на {lang}: {translated}", "info")

    # Форматтер для отображения пользователя как ссылки
    def _user_link_formatter(view, context, model, name):
        if model.user_id:
            url = url_for('user.edit_view', id=model.user_id)
            return Markup(f'<a href="{url}">{model.user_id}</a>')
        return model.user_id

    column_formatters = {
        'user_id': _user_link_formatter
    }


class ScheduledMessageAdmin(UserIdSelectMixin, SecureModelView):
    can_view_details = True
    column_list = ('id', 'user_id', 'text', 'schedule_time', 'sent', 'is_active')
    column_searchable_list = ['text']
    column_filters = ['user_id', 'sent', 'is_active']
    column_default_sort = ('schedule_time', True)
    column_labels = {
        'id': 'ID',
        'user_id': 'Пользователь',
        'text': 'Текст',
        'photo_id': 'ID фото',
        'schedule_time': 'Время отправки',
        'sent': 'Отправлено',
        'is_active': 'Активно'
    }

    form_columns = ('user_id', 'text', 'photo_id', 'schedule_time',
                    'sent', 'is_active')

    # Форматтер для отображения пользователя как ссылки
    def _user_link_formatter(view, context, model, name):
        if model.user_id:
            url = url_for('user.edit_view', id=model.user_id)
            return Markup(f'<a href="{url}">{model.user_id}</a>')
        return model.user_id

    # Форматтер для обрезки длинного текста
    def _text_formatter(view, context, model, name):
        text = model.text or ''
        if len(text) > 50:
            return text[:50] + '...'
        return text

    column_formatters = {
        'user_id': _user_link_formatter,
        'text': _text_formatter
    }


class ReminderAdmin(UserIdSelectMixin, SecureModelView):
    can_view_details = True
    column_list = ('id', 'user_id', 'text', 'due', 'repeat', 'system', 'is_active')
    column_searchable_list = ['text']
    column_filters = ['user_id', 'repeat', 'system', 'is_active']
    column_default_sort = ('due', True)
    column_labels = {
        'id': 'ID',
        'user_id': 'Пользователь',
        'text': 'Текст',
        'due': 'Когда напомнить',
        'repeat': 'Повтор',
        'system': 'Системное',
        'is_active': 'Активно',
        'created_at': 'Создано'
    }

    form_columns = ('user_id', 'text', 'due', 'repeat', 'system', 'is_active')

    # Форматтер для отображения пользователя как ссылки
    def _user_link_formatter(view, context, model, name):
        if model.user_id:
            url = url_for('user.edit_view', id=model.user_id)
            return Markup(f'<a href="{url}">{model.user_id}</a>')
        return model.user_id

    # Форматтер для обрезки длинного текста
    def _text_formatter(view, context, model, name):
        text = model.text or ''
        if len(text) > 50:
            return text[:50] + '...'
        return text

    column_formatters = {
        'user_id': _user_link_formatter,
        'text': _text_formatter
    }


class UserStatsView(BaseView):
    @expose('/')
    def index(self):
        # можно сделать редирект или просто текст
        return self.render('admin/user_stats_index.html')

    @expose('/<int:user_id>')
    def details(self, user_id):
        user = User.query.filter_by(user_id=user_id).first_or_404()

        # нормализация направлений
        direction_map = {
            'owe': 'owe',
            'owed': 'owed',
            'gave': 'owe',
            'took': 'owed'
        }

        stats_by_currency = db.session.query(
            Debt.currency,
            Debt.direction,
            func.sum(Debt.amount).label('total')
        ).filter(
            Debt.user_id == user.user_id,
            Debt.is_active == True,
            Debt.closed == False
        ).group_by(Debt.currency, Debt.direction).all()

        currency_stats = {}
        for currency, direction, total in stats_by_currency:
            norm_dir = direction_map.get(direction, direction)
            if currency not in currency_stats:
                currency_stats[currency] = {'owe': 0, 'owed': 0}
            currency_stats[currency][norm_dir] = float(total or 0)

        balance_by_currency = {
            cur: amounts['owed'] - amounts['owe']
            for cur, amounts in currency_stats.items()
        }

        # HTML прямо в методе
        template = """
                <!doctype html>
        <html lang="ru">
        <head>
            <meta charset="utf-8">
            <title>Статистика пользователя {{ user.user_id }}</title>
            <!-- Bootstrap -->
            <link rel="stylesheet"
                  href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css">
            <style>
                body {
                    background-color: #f8f9fa;
                }
                .card {
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                }
                .card-header {
                    font-weight: 600;
                    font-size: 1.1rem;
                }
                .badge-pill {
                    font-size: 0.9rem;
                    padding: 0.5em 0.8em;
                }
                .currency-box {
                    transition: transform 0.2s ease;
                }
                .currency-box:hover {
                    transform: translateY(-3px);
                    box-shadow: 0 6px 16px rgba(0,0,0,0.12);
                }
            </style>
        </head>
        <body>
        <div class="container mt-4">
            <h1 class="mb-3">📊 Статистика пользователя <span class="text-primary">{{ user.user_id }}</span></h1>
            <p class="text-muted">Язык интерфейса: <strong>{{ user.lang or "не указан" }}</strong></p>

            <!-- Баланс -->
            <div class="card mt-4">
                <div class="card-header bg-primary text-white">💰 Баланс по валютам</div>
                <div class="card-body">
                    {% if balance_by_currency %}
                        <div class="row">
                        {% for cur, balance in balance_by_currency.items() %}
                            <div class="col-md-4 mb-3">
                                <div class="currency-box border rounded p-3 h-100 text-center">
                                    <h5>{{ cur }}</h5>
                                    {% if balance > 0 %}
                                        <span class="badge badge-success badge-pill">+{{ "%.2f"|format(balance) }}</span>
                                    {% elif balance < 0 %}
                                        <span class="badge badge-danger badge-pill">{{ "%.2f"|format(balance) }}</span>
                                    {% else %}
                                        <span class="badge badge-secondary badge-pill">0.00</span>
                                    {% endif %}
                                </div>
                            </div>
                        {% endfor %}
                        </div>
                    {% else %}
                        <p class="text-muted">Нет активных долгов</p>
                    {% endif %}
                </div>
            </div>

            <!-- Детальная статистика -->
            <div class="card mt-4">
                <div class="card-header bg-info text-white">📊 Детальная статистика</div>
                <div class="card-body">
                    {% if currency_stats %}
                        <div class="row">
                        {% for cur, amounts in currency_stats.items() %}
                            <div class="col-md-4 mb-3">
                                <div class="currency-box border rounded p-3 h-100">
                                    <h6 class="mb-2">{{ cur }}</h6>
                                    <p class="mb-1">↗️ Должен: <strong>{{ "%.2f"|format(amounts.owe) }}</strong></p>
                                    <p class="mb-0">↙️ Должны мне: <strong>{{ "%.2f"|format(amounts.owed) }}</strong></p>
                                </div>
                            </div>
                        {% endfor %}
                        </div>
                    {% else %}
                        <p class="text-muted">Нет данных по валютам</p>
                    {% endif %}
                </div>
            </div>

            <!-- Итог -->
            <div class="mt-4">
                <p><strong>Всего долгов:</strong> {{ total_debts }}</p>
                <a href="{{ url_for('admin.index') }}" class="btn btn-secondary">⬅ Назад</a>
            </div>
        </div>
        </body>
        </html>

        """

        return render_template_string(
            template,
            user=user,
            currency_stats=currency_stats,
            balance_by_currency=balance_by_currency,
            total_debts=len([d for d in user.debts if d.is_active and not d.closed])
        )


class TrafficStatsView(BaseView):
    @expose('/')
    def index(self):
        stats = (
            db.session.query(
                User.source,
                func.count(User.user_id).label('total'),
                func.sum(case((User.lang == 'ru', 1), else_=0)).label('ru'),
                func.sum(case((User.lang == 'uz', 1), else_=0)).label('uz'),
            )
            .group_by(User.source)
            .all()
        )

        template = """
        <!doctype html>
        <html lang="ru">
        <head>
            <meta charset="utf-8">
            <title>Источники пользователей</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css">
        </head>
        <body>
        <div class="container mt-4">
            <h1>📢 Источники пользователей</h1>
            <table class="table table-bordered table-striped mt-4">
                <thead class="thead-dark">
                    <tr>
                        <th>Источник</th>
                        <th>Всего</th>
                        <th>Русскоязычных</th>
                        <th>Узбекоязычных</th>
                    </tr>
                </thead>
                <tbody>
                    {% for s in stats %}
                    <tr>
                        <td>{{ s.source or 'Не указан' }}</td>
                        <td>{{ s.total }}</td>
                        <td>{{ s.ru }}</td>
                        <td>{{ s.uz }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <a href="{{ url_for('admin.index') }}" class="btn btn-secondary mt-3">⬅ Назад</a>
        </div>
        </body>
        </html>
        """
        return render_template_string(template, stats=stats)


def create_admin_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'supersecretkey')
    app.config['SQLALCHEMY_DATABASE_URI'] = SYNC_DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['FLASK_ADMIN_SWATCH'] = 'cosmo'

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    Base.query = db.session.query_property()

    admin = Admin(
        app,
        name='💰 DebtBot Admin',
        template_mode='bootstrap4',
        index_view=SecureAdminIndexView(name='Главная', url='/admin')
    )

    admin.add_view(UserAdmin(User, db.session, name='Пользователи', category='Управление'))
    admin.add_view(DebtAdmin(Debt, db.session, name='Долги', category='Управление'))
    admin.add_view(ScheduledMessageAdmin(ScheduledMessage, db.session, name='Сообщения', category='Управление'))
    admin.add_view(UserStatsView(name="", endpoint="user_stats"))
    admin.add_view(TrafficStatsView(name='📢 Источники', category='Статистика'))

    # Кастомный шаблон для главной страницы
    CUSTOM_INDEX_TEMPLATE = '''
    {% extends 'admin/master.html' %}
    {% block body %}
    <div class="container-fluid">
        <h1 class="mt-4">📊 Панель управления DebtBot</h1>

        <div class="row mt-4">
            <div class="col-md-4">
        <div class="card text-white bg-primary mb-3">
            <div class="card-header">👥 Пользователи</div>
            <div class="card-body">
                <h5 class="card-title">{{ total_users }}</h5>
                <p class="card-text">Всего пользователей в системе</p>
            </div>
        </div>
    </div>

    <div class="col-md-4">
        <div class="card text-white bg-success mb-3">
            <div class="card-header">💳 Долги</div>
            <div class="card-body">
                <h5 class="card-title">{{ total_debts }}</h5>
                <p class="card-text">Активных долгов</p>
            </div>
        </div>
    </div>

    <div class="col-md-4">
        <div class="card text-white bg-info mb-3">
            <div class="card-header">📨 Сообщения</div>
            <div class="card-body">
                <h5 class="card-title">{{ total_scheduled }}</h5>
                <p class="card-text">Запланировано к отправке</p>
            </div>
        </div>
    </div>
</div>
        </div>

        <h2 class="mt-5">📈 Статистика по пользователям</h2>

        {% for user_stat in users_stats %}
        <div class="card mt-3">
            <div class="card-header bg-light">
                <h5>
                    👤 Пользователь: {{ user_stat.user.user_id }}
                    <span class="badge badge-secondary">{{ user_stat.user.lang or 'язык не указан' }}</span>
                </h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <h6>💰 Баланс по валютам:</h6>
                        {% if user_stat.balance %}
                            <ul class="list-group">
                            {% for currency, balance in user_stat.balance.items() %}
                                <li class="list-group-item d-flex justify-content-between align-items-center">
                                    {{ currency }}
                                    {% if balance > 0 %}
                                        <span class="badge badge-success badge-pill">+{{ "%.2f"|format(balance) }}</span>
                                    {% elif balance < 0 %}
                                        <span class="badge badge-danger badge-pill">{{ "%.2f"|format(balance) }}</span>
                                    {% else %}
                                        <span class="badge badge-secondary badge-pill">0.00</span>
                                    {% endif %}
                                </li>
                            {% endfor %}
                            </ul>
                        {% else %}
                            <p class="text-muted">Нет активных долгов</p>
                        {% endif %}
                    </div>
                    <div class="col-md-6">
                        <h6>📊 Детальная статистика:</h6>
                        {% if user_stat.currency_stats %}
                            {% for currency, amounts in user_stat.currency_stats.items() %}
                                <div class="mb-2">
                                    <strong>{{ currency }}:</strong><br>
                                    <small>
                                        ↗️ Должен: {{ "%.2f"|format(amounts.owe) }}<br>
                                        ↙️ Должны мне: {{ "%.2f"|format(amounts.owed) }}
                                    </small>
                                </div>
                            {% endfor %}
                        {% endif %}
                        <div class="mt-3">
                            <a href="{{ url_for('user_stats.details', user_id=user_stat.user.user_id) }}" class="btn btn-sm btn-primary">
                                Посмотреть долги ({{ user_stat.total_debts }})
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        {% endfor %}

        {% if not users_stats %}
        <div class="alert alert-info mt-3">
            ℹ️ Пока нет пользователей в системе. Создайте первого пользователя!
        </div>
        {% endif %}
    </div>
    {% endblock %}
    '''

    # Создаем директорию для шаблонов
    import tempfile
    template_dir = os.path.join(tempfile.gettempdir(), 'flask_admin_templates', 'admin')
    os.makedirs(template_dir, exist_ok=True)

    # Сохраняем кастомный шаблон
    with open(os.path.join(template_dir, 'custom_index.html'), 'w', encoding='utf-8') as f:
        f.write(CUSTOM_INDEX_TEMPLATE)

    app.jinja_loader.searchpath.insert(0, os.path.join(tempfile.gettempdir(), 'flask_admin_templates'))

    @app.route("/")
    def index():
        return redirect(url_for("admin.index"))

    # Улучшенная страница логина
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                login_user(AdminUser())
                next_url = request.args.get("next") or url_for("admin.index")
                flash("✅ Успешный вход!", "success")
                return redirect(next_url)
            flash("❌ Неверный логин или пароль", "danger")

        login_template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Вход в DebtBot Admin</title>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
            <style>
                body {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .login-container {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
                    max-width: 400px;
                    width: 100%;
                }
                .login-header {
                    text-align: center;
                    margin-bottom: 30px;
                }
                .login-header h2 {
                    color: #667eea;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="login-container">
                <div class="login-header">
                    <h2>💰 DebtBot Admin</h2>
                    <p class="text-muted">Панель управления</p>
                </div>
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="close" data-dismiss="alert">&times;</button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
                <form method="post">
                    <div class="form-group">
                        <label for="username">Логин</label>
                        <input type="text" class="form-control" id="username" name="username" 
                               placeholder="Введите логин" required autofocus>
                    </div>
                    <div class="form-group">
                        <label for="password">Пароль</label>
                        <input type="password" class="form-control" id="password" name="password" 
                               placeholder="Введите пароль" required>
                    </div>
                    <button type="submit" class="btn btn-primary btn-block">🔐 Войти</button>
                </form>
            </div>
            <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.5.2/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
        '''
        return render_template_string(login_template)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("👋 Вы вышли из системы", "info")
        return redirect(url_for("login"))

    with app.app_context():
        Base.metadata.create_all(bind=db.engine)

    return app