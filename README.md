# 💸 Debt Manager Telegram Bot

A Telegram bot built with **Aiogram** for tracking and managing personal or shared debts.  
Users can record who owes whom, track repayments, and view current balances — all within Telegram.

---

## 📦 Features

- Add new debts between users  
- Track repayments and partial payments  
- View current balances and debt history  
- Inline buttons for quick actions  
- Admin tools for managing users and clearing records  

---

## ⚙️ Deployment

### 1. Environment setup
sudo nano .env
pip install -r requirements.txt
python -m app.bot.init

### 2. Database migrations
Generate a new migration:


alembic revision --autogenerate -m "init"
Apply migrations:


alembic upgrade head
## 🗂 Project Structure
app/db → database models and debt logic

app/bot/routers → Telegram update handlers

app/bot/init → bot startup and dispatcher setup

## 🛠 Tech Stack
Python 3.10+

Aiogram

PostgreSQL

Alembic

Docker (optional)
