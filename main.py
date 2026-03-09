# main.py
import threading
import time
import signal
import sys

# Исправлено: импортируем функции запуска
from telegram_bot import run_telegram_bot
from discord_bot import run_discord_bot

def signal_handler(sig, frame):
    # Обработчик Ctrl+C для корректного завершения
    print("\n👋 Получен сигнал остановки. Завершаем работу...")
    sys.exit(0)

if __name__ == "__main__":
    # Устанавливаем обработчик сигнала
    signal.signal(signal.SIGINT, signal_handler)
    
    print("🚀 Запуск бота Соль...")
    print("📢 Нажми Ctrl+C для остановки")
    
    # Запускаем Telegram бота в отдельном потоке
    tg_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    tg_thread.start()
    
    # Запускаем Discord бота в основном потоке
    try:
        run_discord_bot()
    except KeyboardInterrupt:
        print("👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
