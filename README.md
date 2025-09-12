## 🚀 Запуск и остановка

### Запустить бота
sudo systemctl start telegram-bot.service

### Остановить бота
sudo systemctl stop telegram-bot.service

### Перезапустить бота
sudo systemctl restart telegram-bot.service

### Проверить статус
sudo systemctl status telegram-bot.service

---

## 🔄 Автозапуск при старте сервера
sudo systemctl enable telegram-bot.service

---

## 📜 Логи

### Смотреть последние логи
journalctl -u telegram-bot.service -e

### Смотреть логи за последние 2 дня
journalctl -u telegram-bot.service --since "2 days ago"

### Смотреть логи в реальном времени
tail -f /opt/telegram_bot/bot.log

---