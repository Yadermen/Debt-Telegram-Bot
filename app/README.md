Ф# 🔄 Перечитать конфигурацию systemd (после правок unit-файла)
sudo systemctl daemon-reload

# 🚀 Запустить бота
sudo systemctl start debt-bot.service

# ⏹ Остановить бота
sudo systemctl stop debt-bot.service

# ♻️ Перезапустить бота
sudo systemctl restart debt-bot.service

# 📊 Проверить статус бота
sudo systemctl status debt-bot.service

# 🔄 Включить автозапуск при старте сервера
sudo systemctl enable debt-bot.service

# 📜 Смотреть последние логи
journalctl -u debt-bot.service -e

# 📜 Логи за последние 2 дня
journalctl -u debt-bot.service --since "2 days ago"

# 📡 Логи в реальном времени
journalctl -u debt-bot.service -f

