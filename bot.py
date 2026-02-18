import telebot
from telebot import types
from flask import Flask, request, jsonify
import json
import threading

# ========== ТВОИ ДАННЫЕ ==========
BOT_TOKEN = "8462463429:AAHFZh-P1jFLU47ll6jx8QuSyNI-oRtu5K0"
ADMIN_CHAT_ID = "8462463429"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ========== СЕРВЕР ДЛЯ ЗАКАЗОВ ==========
@app.route('/order', methods=['POST'])
def receive_order():
    try:
        data = request.json
        items = data.get('items', [])
        total = data.get('total', 0)
        user_id = data.get('user_id', 'неизвестно')

        msg = f"🆕 **Новый заказ!**\n"
        msg += f"👤 Пользователь: {user_id}\n"
        msg += f"💰 Сумма: {total} руб.\n"
        msg += f"📦 Состав:\n"
        for item in items:
            msg += f"  • {item['name']} — {item['price']} руб.\n"

        bot.send_message(ADMIN_CHAT_ID, msg, parse_mode='Markdown')
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== КНОПКА МЕНЮ ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton(
        "🍔 Открыть меню",
        web_app=types.WebAppInfo("https://food-samirapp.pages.dev")
    )
    markup.add(btn)
    bot.send_message(
        message.chat.id,
        "👋 Привет! Нажми кнопку ниже, чтобы заказать еду.",
        reply_markup=markup
    )

# ========== ЗАПУСК ==========
def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Бот запущен...")
    bot.infinity_polling()