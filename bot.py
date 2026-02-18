import telebot
from telebot import types
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import os
import uuid
import database as db

# ========== ТВОИ ДАННЫЕ ==========
BOT_TOKEN = "8462463429:AAHFZh-P1jFLU47ll6jx8QuSyNI-oRtu5K0"
ADMIN_CHAT_ID = "8180932270"
YOOMONEY_WALLET = "4100119475243191"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# Запускаем бота в фоне
threading.Thread(target=bot.infinity_polling, daemon=True).start()

# ========== МАРШРУТЫ FLASK (без изменений) ==========
@app.route('/')
def index():
    return "Бот для доставки еды работает! 🚀"

@app.route('/order', methods=['POST', 'OPTIONS'])
def receive_order():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        items = data.get('items', [])
        total = data.get('total', 0)
        user_id = data.get('user_id', 'неизвестно')
        address = data.get('address', '')
        phone = data.get('phone', '')
        geo = data.get('geo', None)

        if geo:
            geo_link = f"https://maps.google.com/?q={geo['lat']},{geo['lon']}"
            address = geo_link

        order_id = str(uuid.uuid4())[:8]
        db.save_order(order_id, user_id, items, total, address, phone)

        # Отправляем уведомление админу
        msg = f"🆕 **Новый заказ #{order_id}**\n"
        msg += f"👤 Пользователь: {user_id}\n"
        msg += f"💰 Сумма: {total} руб.\n📦 Состав:\n"
        for item in items:
            msg += f"  • {item['name']} — {item['price']} руб.\n"
        msg += f"🏠 Адрес: {address}\n📞 Телефон: {phone}\n"
        bot.send_message(ADMIN_CHAT_ID, msg, parse_mode='Markdown')

        # Отправляем заказ всем активным курьерам
        couriers = db.get_active_couriers()
        for courier_id in couriers:
            try:
                bot.send_message(
                    courier_id,
                    f"🚚 **Новый заказ!**\n"
                    f"№ {order_id}\n"
                    f"💰 Сумма: {total} руб.\n"
                    f"🏠 Адрес: {address}\n"
                    f"📞 Телефон клиента: {phone}\n\n"
                    f"Чтобы принять заказ, отправьте:\n`/accept {order_id}`",
                    parse_mode='Markdown'
                )
            except:
                pass

        return jsonify({"status": "ok", "order_id": order_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/create_payment', methods=['POST', 'OPTIONS'])
def create_payment():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        order_id = data.get('order_id')
        amount = data.get('amount')
        if not amount or not order_id:
            return jsonify({"error": "Не указана сумма или номер заказа"}), 400

        payment_link = (
            f"https://yoomoney.ru/quickpay/confirm.xml?"
            f"receiver={YOOMONEY_WALLET}&"
            f"quickpay-form=shop&"
            f"targets=Заказ%20№{order_id}&"
            f"paymentType=PC&"
            f"sum={amount}&"
            f"label={order_id}&"
            f"successURL=https://t.me/dostavka_edy_na_dom_bot"
        )
        return jsonify({"status": "ok", "payment_link": payment_link, "order_id": order_id, "amount": amount})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== КОМАНДЫ БОТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    user = db.get_user(message.from_user.id)
    if user:
        # Если пользователь уже зарегистрирован, показываем его меню
        if user['role'] == 'client':
            show_client_menu(message)
        else:
            show_courier_menu(message)
        return

    # Новый пользователь: предлагаем выбрать роль
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("👤 Я хочу заказать еду", "🛵 Я доставщик")
    bot.send_message(message.chat.id, "Добро пожаловать! Кто вы?", reply_markup=markup)
    bot.register_next_step_handler(message, choose_role)

def choose_role(message):
    user_id = message.from_user.id
    if message.text == "👤 Я хочу заказать еду":
        role = 'client'
        markup = types.ReplyKeyboardRemove()
        bot.send_message(user_id, "Введите ваше имя:", reply_markup=markup)
        bot.register_next_step_handler(message, get_name, role)
    elif message.text == "🛵 Я доставщик":
        role = 'courier'
        markup = types.ReplyKeyboardRemove()
        bot.send_message(user_id, "Введите ваше имя:", reply_markup=markup)
        bot.register_next_step_handler(message, get_name, role)
    else:
        bot.send_message(user_id, "Пожалуйста, выберите роль, используя кнопки.")
        start(message)

def get_name(message, role):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "Имя не может быть пустым. Попробуйте снова /start")
        return
    bot.send_message(message.chat.id, "Введите ваш номер телефона:")
    bot.register_next_step_handler(message, get_phone, role, name)

def get_phone(message, role, name):
    phone = message.text.strip()
    db.add_user(message.from_user.id, role, name, phone)
    bot.send_message(message.chat.id, f"✅ Вы зарегистрированы как {role}!")
    if role == 'client':
        show_client_menu(message)
    else:
        show_courier_menu(message)

# ---------- Меню клиента ----------
def show_client_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton(
        "🍔 Открыть меню",
        web_app=types.WebAppInfo("https://food-samirapp.pages.dev")
    )
    markup.add(btn)
    bot.send_message(
        message.chat.id,
        "👋 Нажми кнопку ниже, чтобы заказать еду.",
        reply_markup=markup
    )

# ---------- Меню доставщика ----------
def show_courier_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚚 На линии", "⏸ Не на линии", "📋 Доступные заказы")
    bot.send_message(message.chat.id, "Меню доставщика:", reply_markup=markup)

@bot.message_handler(regexp="^🚚 На линии$")
def courier_online(message):
    db.set_courier_active(message.from_user.id, True)
    bot.send_message(message.chat.id, "✅ Вы на линии. Теперь вам будут приходить уведомления о новых заказах.")

@bot.message_handler(regexp="^⏸ Не на линии$")
def courier_offline(message):
    db.set_courier_active(message.from_user.id, False)
    bot.send_message(message.chat.id, "⏸ Вы не на линии. Новые заказы приходить не будут.")

@bot.message_handler(regexp="^📋 Доступные заказы$")
def show_available_orders(message):
    orders = db.get_new_orders()
    if not orders:
        bot.send_message(message.chat.id, "Нет доступных заказов.")
        return
    for order in orders:
        items_str = "\n".join([f"• {i['name']} - {i['price']} руб." for i in order['items']])
        msg = f"🆕 **Заказ #{order['order_id']}**\n"
        msg += f"💰 Сумма: {order['total']} руб.\n"
        msg += f"📦 Состав:\n{items_str}\n"
        msg += f"🏠 Адрес: {order['address']}\n"
        msg += f"📞 Телефон: {order['phone']}\n\n"
        msg += f"Чтобы принять, отправьте:\n`/accept {order['order_id']}`"
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['accept'])
def accept_order(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Укажите номер заказа: /accept ABC123")
            return
        order_id = parts[1]
        user = db.get_user(message.from_user.id)
        if not user or user['role'] != 'courier':
            bot.reply_to(message, "❌ Только доставщики могут принимать заказы.")
            return
        if not user['is_active']:
            bot.reply_to(message, "❌ Вы не на линии. Включите режим «На линии» в меню.")
            return
        success = db.take_order(order_id, message.from_user.id)
        if success:
            bot.send_message(message.chat.id, f"✅ Заказ #{order_id} принят! Свяжитесь с клиентом.")
            # Уведомляем админа
            bot.send_message(ADMIN_CHAT_ID, f"✅ Заказ #{order_id} принят курьером {message.from_user.id}")
        else:
            bot.reply_to(message, "❌ Не удалось принять заказ (возможно, его уже кто-то взял).")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['confirm'])
def confirm_payment(message):
    # как было ранее
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Укажи номер заказа: /confirm 123")
            return
        order_id = parts[1]
        order = db.get_order(order_id)  # нужна функция в database.py
        if not order:
            bot.reply_to(message, "❌ Заказ не найден")
            return
        if order['status'] == 'paid':
            bot.reply_to(message, "✅ Этот заказ уже оплачен")
            return
        db.mark_order_paid(order_id)
        bot.reply_to(message, f"✅ Заказ #{order_id} отмечен как оплаченный!")
        bot.send_message(ADMIN_CHAT_ID, f"💰 Заказ #{order_id} оплачен!")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)