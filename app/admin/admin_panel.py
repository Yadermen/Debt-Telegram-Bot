# app/admin/admin_panel.py
"""
Веб-интерфейс администратора для Telegram бота
"""
import asyncio
import threading
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import (
    ADMIN_HOST, ADMIN_PORT, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_SECRET_KEY,
    ADMIN_SESSION_TIMEOUT, ADMIN_ENABLE_EXPORT, ADMIN_MAX_EXPORT_ROWS,
    ADMIN_PAGE_SIZE, ADMIN_THEME, ADMIN_ALLOWED_IPS
)
from app.database import Base
from app.database.connection import engine

# Глобальные переменные
app = Flask(__name__)
app.secret_key = ADMIN_SECRET_KEY
admin_thread = None


def check_ip_allowed():
    """Проверка разрешенных IP адресов"""
    if not ADMIN_ALLOWED_IPS:
        return True

    client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    return client_ip in ADMIN_ALLOWED_IPS


def login_required(f):
    """Декоратор для проверки авторизации"""

    def decorated_function(*args, **kwargs):
        if not check_ip_allowed():
            return "Доступ запрещен с вашего IP адреса", 403

        if 'logged_in' not in session:
            return redirect(url_for('login'))

        # Проверка времени сессии
        if 'login_time' in session:
            login_time = datetime.fromisoformat(session['login_time'])
            if datetime.now() - login_time > timedelta(hours=ADMIN_SESSION_TIMEOUT):
                session.clear()
                flash('Сессия истекла. Войдите заново.', 'warning')
                return redirect(url_for('login'))

        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


# HTML шаблоны
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ панель - Вход</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .login-container { min-height: 100vh; }
        .card { border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
    </style>
</head>
<body>
    <div class="container login-container d-flex align-items-center justify-content-center">
        <div class="row w-100">
            <div class="col-md-6 col-lg-4 mx-auto">
                <div class="card">
                    <div class="card-body p-5">
                        <div class="text-center mb-4">
                            <h2 class="fw-bold">🔐 Админ панель</h2>
                            <p class="text-muted">Telegram Bot Management</p>
                        </div>

                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                                        {{ message }}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}

                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">Логин</label>
                                <input type="text" class="form-control" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Пароль</label>
                                <input type="password" class="form-control" name="password" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Войти</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ панель - Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .sidebar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .nav-link { color: rgba(255,255,255,0.8) !important; }
        .nav-link:hover, .nav-link.active { color: white !important; background: rgba(255,255,255,0.1); }
        .card { box-shadow: 0 2px 10px rgba(0,0,0,0.1); border: none; }
        .stat-card { transition: transform 0.2s; }
        .stat-card:hover { transform: translateY(-5px); }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <!-- Боковая панель -->
            <div class="col-md-2 sidebar p-0">
                <div class="p-3">
                    <h4 class="text-white">🤖 Bot Admin</h4>
                </div>
                <nav class="nav flex-column">
                    <a class="nav-link active" href="{{ url_for('dashboard') }}">
                        <i class="fas fa-tachometer-alt"></i> Dashboard
                    </a>
                    <a class="nav-link" href="{{ url_for('users') }}">
                        <i class="fas fa-users"></i> Пользователи
                    </a>
                    <a class="nav-link" href="{{ url_for('debts') }}">
                        <i class="fas fa-money-bill-wave"></i> Долги
                    </a>
                    <a class="nav-link" href="{{ url_for('broadcast') }}">
                        <i class="fas fa-bullhorn"></i> Рассылка
                    </a>
                    <a class="nav-link" href="{{ url_for('settings') }}">
                        <i class="fas fa-cog"></i> Настройки
                    </a>
                    <hr class="my-3" style="border-color: rgba(255,255,255,0.3);">
                    <a class="nav-link" href="{{ url_for('logout') }}">
                        <i class="fas fa-sign-out-alt"></i> Выход
                    </a>
                </nav>
            </div>

            <!-- Основной контент -->
            <div class="col-md-10">
                <div class="container-fluid p-4">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h2>📊 Панель управления</h2>
                        <div class="text-muted">
                            <i class="fas fa-clock"></i> {{ current_time }}
                        </div>
                    </div>

                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}

                    <!-- Статистика -->
                    <div class="row mb-4">
                        <div class="col-md-3">
                            <div class="card stat-card text-center p-3" style="background: linear-gradient(135deg, #667eea, #764ba2); color: white;">
                                <i class="fas fa-users fa-2x mb-2"></i>
                                <h3>{{ stats.users }}</h3>
                                <small>Пользователей</small>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card stat-card text-center p-3" style="background: linear-gradient(135deg, #f093fb, #f5576c); color: white;">
                                <i class="fas fa-money-bill-wave fa-2x mb-2"></i>
                                <h3>{{ stats.debts }}</h3>
                                <small>Активных долгов</small>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card stat-card text-center p-3" style="background: linear-gradient(135deg, #4facfe, #00f2fe); color: white;">
                                <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                                <h3>{{ stats.overdue_debts }}</h3>
                                <small>Просроченных</small>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card stat-card text-center p-3" style="background: linear-gradient(135deg, #43e97b, #38f9d7); color: white;">
                                <i class="fas fa-chart-line fa-2x mb-2"></i>
                                <h3>{{ stats.total_amount }}</h3>
                                <small>Общая сумма</small>
                            </div>
                        </div>
                    </div>

                    <!-- Последние пользователи -->
                    <div class="row">
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header">
                                    <h5><i class="fas fa-users"></i> Новые пользователи</h5>
                                </div>
                                <div class="card-body">
                                    {% if recent_users %}
                                        <div class="list-group list-group-flush">
                                            {% for user in recent_users %}
                                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                                    <div>
                                                        <strong>{{ user.user_id }}</strong>
                                                        <br>
                                                        <small class="text-muted">Язык: {{ user.lang }}</small>
                                                    </div>
                                                    <small class="text-muted">{{ user.created_at }}</small>
                                                </div>
                                            {% endfor %}
                                        </div>
                                    {% else %}
                                        <p class="text-muted">Нет данных</p>
                                    {% endif %}
                                </div>
                            </div>
                        </div>

                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header">
                                    <h5><i class="fas fa-exclamation-triangle"></i> Просроченные долги</h5>
                                </div>
                                <div class="card-body">
                                    {% if overdue_debts %}
                                        <div class="list-group list-group-flush">
                                            {% for debt in overdue_debts %}
                                                <div class="list-group-item">
                                                    <div class="d-flex justify-content-between">
                                                        <strong>{{ debt.person }}</strong>
                                                        <span class="badge bg-danger">{{ debt.amount }} {{ debt.currency }}</span>
                                                    </div>
                                                    <small class="text-muted">
                                                        Пользователь: {{ debt.user_id }} | Срок: {{ debt.due }}
                                                    </small>
                                                </div>
                                            {% endfor %}
                                        </div>
                                    {% else %}
                                        <p class="text-muted">Нет просроченных долгов</p>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

BROADCAST_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Рассылка</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2><i class="fas fa-bullhorn"></i> Рассылка сообщений</h2>
            <a href="{{ url_for('dashboard') }}" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left"></i> Назад
            </a>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5>Создать рассылку</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST" action="{{ url_for('broadcast') }}" enctype="multipart/form-data">
                            <div class="mb-3">
                                <label class="form-label">Текст сообщения</label>
                                <textarea class="form-control" name="message_text" rows="6" required 
                                          placeholder="Введите текст рассылки..."></textarea>
                            </div>

                            <div class="mb-3">
                                <label class="form-label">Изображение (опционально)</label>
                                <input type="file" class="form-control" name="photo" accept="image/*">
                                <small class="form-text text-muted">Поддерживаются: JPG, PNG, GIF</small>
                            </div>

                            <div class="mb-3">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" name="schedule" id="schedule">
                                    <label class="form-check-label" for="schedule">
                                        Запланировать отправку
                                    </label>
                                </div>
                            </div>

                            <div class="mb-3" id="schedule_time" style="display: none;">
                                <label class="form-label">Дата и время отправки</label>
                                <input type="datetime-local" class="form-control" name="schedule_datetime">
                            </div>

                            <div class="d-grid gap-2">
                                <button type="submit" class="btn btn-primary">
                                    <i class="fas fa-paper-plane"></i> Отправить рассылку
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h6>Информация</h6>
                    </div>
                    <div class="card-body">
                        <p><strong>Активных пользователей:</strong> {{ user_count }}</p>
                        <p><strong>Примерное время рассылки:</strong> {{ estimated_time }} сек</p>
                        <hr>
                        <small class="text-muted">
                            💡 Совет: Проверьте текст перед отправкой. 
                            Отменить рассылку после запуска невозможно.
                        </small>
                    </div>
                </div>

                <div class="card mt-3">
                    <div class="card-header">
                        <h6>История рассылок</h6>
                    </div>
                    <div class="card-body">
                        {% if broadcast_history %}
                            {% for broadcast in broadcast_history %}
                                <div class="border-bottom py-2">
                                    <small>
                                        <strong>{{ broadcast.date }}</strong><br>
                                        Успешно: {{ broadcast.success }}<br>
                                        Ошибки: {{ broadcast.errors }}
                                    </small>
                                </div>
                            {% endfor %}
                        {% else %}
                            <small class="text-muted">История пуста</small>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.getElementById('schedule').addEventListener('change', function() {
            const scheduleTime = document.getElementById('schedule_time');
            scheduleTime.style.display = this.checked ? 'block' : 'none';
        });
    </script>
</body>
</html>
"""


# Функции для получения данных



# Дополнительные шаблоны
USERS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Управление пользователями</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <div class="container-fluid mt-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2><i class="fas fa-users"></i> Управление пользователями</h2>
            <a href="{{ url_for('dashboard') }}" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left"></i> Назад к Dashboard
            </a>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5>Список пользователей ({{ total_users }})</h5>
                <div class="input-group" style="width: 300px;">
                    <input type="text" class="form-control" id="searchInput" placeholder="Поиск по ID...">
                    <button class="btn btn-outline-secondary" type="button">
                        <i class="fas fa-search"></i>
                    </button>
                </div>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead>
                            <tr>
                                <th>ID пользователя</th>
                                <th>Язык</th>
                                <th>Время уведомлений</th>
                                <th>Статус</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for user in users %}
                                <tr>
                                    <td>
                                        <strong>{{ user.user_id }}</strong>
                                        <br>
                                        <small class="text-muted">
                                            <i class="fas fa-calendar"></i> Регистрация
                                        </small>
                                    </td>
                                    <td>
                                        <span class="badge bg-primary">{{ user.lang.upper() }}</span>
                                    </td>
                                    <td>
                                        {% if user.notify_time %}
                                            <i class="fas fa-clock text-success"></i> {{ user.notify_time }}
                                        {% else %}
                                            <span class="text-muted">Не установлено</span>
                                        {% endif %}
                                    </td>
                                    <td>
                                        <span class="badge bg-success">Активный</span>
                                    </td>
                                    <td>
                                        <div class="btn-group btn-group-sm">
                                            <button class="btn btn-outline-primary" onclick="viewUser({{ user.user_id }})">
                                                <i class="fas fa-eye"></i>
                                            </button>
                                            <button class="btn btn-outline-info" onclick="sendMessage({{ user.user_id }})">
                                                <i class="fas fa-envelope"></i>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

                {% if pages > 1 %}
                    <nav aria-label="Навигация по страницам">
                        <ul class="pagination justify-content-center">
                            {% for page_num in range(1, pages + 1) %}
                                <li class="page-item {{ 'active' if page_num == current_page }}">
                                    <a class="page-link" href="?page={{ page_num }}">{{ page_num }}</a>
                                </li>
                            {% endfor %}
                        </ul>
                    </nav>
                {% endif %}
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function viewUser(userId) {
            alert('Просмотр пользователя: ' + userId);
        }

        function sendMessage(userId) {
            const message = prompt('Введите сообщение для пользователя ' + userId + ':');
            if (message) {
                // Здесь можно отправить AJAX запрос для отправки сообщения
                alert('Сообщение будет отправлено: ' + message);
            }
        }

        // Поиск пользователей
        document.getElementById('searchInput').addEventListener('input', function() {
            const filter = this.value.toLowerCase();
            const rows = document.querySelectorAll('tbody tr');

            rows.forEach(row => {
                const userId = row.cells[0].textContent.toLowerCase();
                if (userId.includes(filter)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    </script>
</body>
</html>
"""


# Обновление маршрута пользователей
@app.route('/admin/users')
@login_required
def users_list():
    """Страница управления пользователями"""
    try:
        page = int(request.args.get('page', 1))
        per_page = ADMIN_PAGE_SIZE

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from app.database import get_all_users
        all_users = loop.run_until_complete(get_all_users())

        loop.close()

        # Пагинация
        total_users = len(all_users)
        start = (page - 1) * per_page
        end = start + per_page
        users_page = all_users[start:end]
        total_pages = (total_users + per_page - 1) // per_page

        return render_template_string(
            USERS_TEMPLATE,
            users=users_page,
            total_users=total_users,
            current_page=page,
            pages=total_pages
        )
    except Exception as e:
        flash(f'Ошибка загрузки пользователей: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


if __name__ == "__main__":
    # Прямой запуск админ панели (для тестирования)
    print("🚀 Запуск админ панели в режиме разработки...")
    app.run(
        host=ADMIN_HOST,
        port=ADMIN_PORT,
        debug=True
    )




def start_admin_in_background():
    """Запуск админки в фоновом режиме"""
    # Получаем настройки из переменных окружения
    admin_host = os.getenv('ADMIN_HOST', '0.0.0.0')
    admin_port = int(os.getenv('ADMIN_PORT', '8080'))

    def run_admin_thread():
        try:
            # Создание таблиц если их нет
            Base.metadata.create_all(engine)


            print(f"🚀 Админка запущена на http://{admin_host}:{admin_port}/admin")
            print(f"👤 Логин: {ADMIN_USERNAME}")
            print(f"🔑 Пароль: {ADMIN_PASSWORD}")

            app.run(debug=False, host=admin_host, port=admin_port, use_reloader=False)
        except Exception as e:
            print(f"❌ Ошибка запуска админки: {e}")

    admin_thread = threading.Thread(target=run_admin_thread, daemon=True)
    admin_thread.start()
    return admin_thread