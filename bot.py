import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import F
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import json
import logging
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Webhook настройки
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + WEBHOOK_PATH if os.getenv("RENDER_EXTERNAL_URL") else None

async def on_startup():
    """Действия при запуске бота"""
    print("🤖 Бот запускается...")
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown():
    """Действия при остановке бота"""
    print("🛑 Бот останавливается...")
    if WEBHOOK_URL:
        await bot.delete_webhook()
    await bot.session.close()
    print("✅ Бот остановлен")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ⚙️ Настройки
ADMIN_ID = 2133091842
FREE_CHAT_LIMIT = 10
TRIAL_HOURS = 24

# Хранилище
waiting_users = set()
waiting_users_by_gender = {
    'male': set(),
    'female': set(),
    'any': set()
}
active_chats = {}
users = {}
broadcast_data = {}

# 🆕 Хранилище для жалоб и истории чатов
reports = {}
chat_history = {}
banned_users = set()
report_counter = 1

# 🆕 Хранилище для раскрытия юзернеймов
username_requests = {}

# ==========================
# 📋 Меню
# ==========================

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти собеседника"), KeyboardButton(text="🔎 Поиск по полу")],
            [KeyboardButton(text="❌ Остановить чат"), KeyboardButton(text="🚨 Пожаловаться")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="ℹ️ Моя подписка")],
            [KeyboardButton(text="💎 Купить подписку")]
        ],
        resize_keyboard=True
    )

def chat_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Показать username"), KeyboardButton(text="🚨 Пожаловаться")],
            [KeyboardButton(text="❌ Остановить чат")]
        ],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="⚙️ Управление подписками")],
            [KeyboardButton(text="🚨 Жалобы"), KeyboardButton(text="🚫 Заблокированные")],
            [KeyboardButton(text="🚪 Выйти из админ-панели")]
        ],
        resize_keyboard=True
    )

def rules_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять правила", callback_data="accept_rules")],
        [InlineKeyboardButton(text="📜 Прочитать правила", callback_data="read_rules")]
    ])

def username_request_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Раскрыть username", callback_data="accept_username")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data="reject_username")]
    ])

def settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Выбрать пол", callback_data="set_gender")],
        [InlineKeyboardButton(text="📜 Правила", callback_data="show_rules")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def gender_selection_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужской", callback_data="gender_male")],
        [InlineKeyboardButton(text="👩 Женский", callback_data="gender_female")],
        [InlineKeyboardButton(text="❌ Не указывать", callback_data="gender_none")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_settings")]
    ])

def search_by_gender_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Искать мужчину", callback_data="search_male")],
        [InlineKeyboardButton(text="👩 Искать женщину", callback_data="search_female")],
        [InlineKeyboardButton(text="🤷 Искать любого", callback_data="search_any")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])

def report_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚨 Оскорбления", callback_data="report_insults")],
        [InlineKeyboardButton(text="📵 Неприемлемый контент", callback_data="report_content")],
        [InlineKeyboardButton(text="🎣 Спам/Реклама", callback_data="report_spam")],
        [InlineKeyboardButton(text="👤 Другое", callback_data="report_other")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_chat")]
    ])

def admin_report_menu(report_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Просмотреть чат", callback_data=f"view_chat_{report_id}")],
        [InlineKeyboardButton(text="🚫 Заблокировать обоих", callback_data=f"ban_both_{report_id}")],
        [InlineKeyboardButton(text="🚫 Заблокировать жалобщика", callback_data=f"ban_reporter_{report_id}")],
        [InlineKeyboardButton(text="🚫 Заблокировать нарушителя", callback_data=f"ban_reported_{report_id}")],
        [InlineKeyboardButton(text="✅ Отклонить жалобу", callback_data=f"reject_report_{report_id}")],
        [InlineKeyboardButton(text="➡️ Следующая жалоба", callback_data="next_report")]
    ])

def subscription_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 1 день — 5", callback_data="buy_1")],
        [InlineKeyboardButton(text="⭐ 7 дней — 35", callback_data="buy_7")],
        [InlineKeyboardButton(text="⭐ 30 дней — 150", callback_data="buy_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

def subscription_management_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить подписку", callback_data="admin_add_sub")],
        [InlineKeyboardButton(text="❌ Снять подписку", callback_data="admin_remove_sub")],
        [InlineKeyboardButton(text="📋 Список подписок", callback_data="admin_list_subs")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
    ])

def broadcast_confirmation():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")]
    ])

# ==========================
# 📜 ПРАВИЛА
# ==========================

RULES_TEXT = """
📜 <b>ПРАВИЛА ИСПОЛЬЗОВАНИЯ АНОНИМНОГО ЧАТА</b>

1. <b>Уважайте других пользователей</b>
   🚫 Запрещены оскорбления, угрозы, травля
   🚫 Не допускается дискриминация по любым признакам

2. <b>Соблюдайте возрастные ограничения</b>
   📵 Запрещен контент 18+
   📵 Нельзя обсуждать запрещенные темы

3. <b>Не нарушайте приватность</b>
   🔒 Не требуйте личную информацию
   🔒 Не распространяйте данные других пользователей

4. <b>Без спама и рекламы</b>
   🎣 Запрещена коммерческая реклама
   🎣 Нельзя присылать ссылки на сторонние ресурсы

5. <b>Взаимное уважение</b>
   🤝 Общайтесь так, как хотите чтобы общались с вами
   🤝 Помните - по ту сторону такой же человек

<b>Нарушение правил ведет к блокировке!</b>

✅ Нажимая \"Принять правила\", вы соглашаетесь с ними.
"""

# ==========================
# 📌 Utility
# ==========================

def get_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "free_chats_today": FREE_CHAT_LIMIT,
            "subscription_until": datetime.now() + timedelta(hours=TRIAL_HOURS),
            "last_reset": datetime.now().date(),
            "trial_given": True,
            "gender": None,
            "search_gender": "any",
            "warnings": 0,
            "reports_received": 0,
            "reports_made": 0,
            "rules_accepted": False,
            "rules_accepted_date": None,
            "username_requests_count": 0,
            "last_username_request": None
        }
    return users[user_id]

def reset_daily_limits():
    today = datetime.now().date()
    for user_data in users.values():
        if user_data["last_reset"] < today:
            user_data["free_chats_today"] = FREE_CHAT_LIMIT
            user_data["last_reset"] = today

def has_active_subscription(user):
    return user["subscription_until"] and user["subscription_until"] > datetime.now()

def add_subscription(user_id, days):
    user = get_user(user_id)
    if user["subscription_until"] < datetime.now():
        user["subscription_until"] = datetime.now() + timedelta(days=days)
    else:
        user["subscription_until"] += timedelta(days=days)

def get_gender_text(gender):
    gender_texts = {
        'male': '👨 Мужской',
        'female': '👩 Женский', 
        None: '❌ Не указан'
    }
    return gender_texts.get(gender, '❌ Не указан')

def get_search_gender_text(search_gender):
    search_texts = {
        'male': '👨 Мужчину',
        'female': '👩 Женщину',
        'any': '🤷 Любого'
    }
    return search_texts.get(search_gender, '🤷 Любого')

def is_user_banned(user_id):
    return user_id in banned_users

def has_accepted_rules(user_id):
    user = get_user(user_id)
    return user.get("rules_accepted", False)

def can_request_username(user_id):
    user = get_user(user_id)
    if user["last_username_request"] is None:
        return True
    time_since_last = datetime.now() - user["last_username_request"]
    return time_since_last.total_seconds() >= 600

def add_to_chat_history(user_id, message_text):
    if user_id not in chat_history:
        chat_history[user_id] = []
    
    chat_history[user_id].append({
        "text": message_text,
        "timestamp": datetime.now()
    })
    
    if len(chat_history[user_id]) > 100:
        chat_history[user_id] = chat_history[user_id][-100:]

def get_chat_history(user_id, limit=20):
    if user_id in chat_history:
        return chat_history[user_id][-limit:]
    return []

def create_report(user_id, reported_user_id, reason):
    global report_counter
    
    report_id = report_counter
    report_counter += 1
    
    user_history = get_chat_history(user_id, 15)
    reported_history = get_chat_history(reported_user_id, 15)
    
    combined_history = []
    for msg in user_history:
        combined_history.append({
            "user": user_id,
            "text": msg["text"],
            "timestamp": msg["timestamp"]
        })
    for msg in reported_history:
        combined_history.append({
            "user": reported_user_id,
            "text": msg["text"],
            "timestamp": msg["timestamp"]
        })
    
    combined_history.sort(key=lambda x: x["timestamp"])
    
    reports[report_id] = {
        "user_id": user_id,
        "reported_user_id": reported_user_id,
        "reason": reason,
        "chat_history": combined_history,
        "timestamp": datetime.now(),
        "status": "new"
    }
    
    get_user(user_id)["reports_made"] += 1
    get_user(reported_user_id)["reports_received"] += 1
    
    return report_id

def find_gender_partner(user_id, wanted_gender):
    user = get_user(user_id)
    user_gender = user.get('gender')
    
    for gender_queue in ['male', 'female', 'any']:
        for partner_id in waiting_users_by_gender[gender_queue]:
            if partner_id == user_id:
                continue
                
            partner_user = get_user(partner_id)
            partner_gender = partner_user.get('gender')
            partner_wanted_gender = partner_user.get('search_gender', 'any')
            
            if wanted_gender != 'any':
                if partner_gender == wanted_gender:
                    if partner_wanted_gender == 'any' or partner_wanted_gender == user_gender:
                        return partner_id, gender_queue
            else:
                if partner_wanted_gender == 'any' or partner_wanted_gender == user_gender:
                    return partner_id, gender_queue
    
    return None, None

# ==========================
# 🚀 КОМАНДЫ И ОСНОВНЫЕ ХЕНДЛЕРЫ
# ==========================

@dp.message(Command("start"))
async def start_command(message: Message):
    if is_user_banned(message.from_user.id):
        await message.answer("🚫 Вы заблокированы и не можете использовать бота.")
        return
    
    user = get_user(message.from_user.id)
    
    if not has_accepted_rules(message.from_user.id):
        await message.answer(
            "👋 Добро пожаловать в анонимный чат!\n\n"
            "📜 <b>Для использования бота необходимо принять правила</b>",
            parse_mode='HTML',
            reply_markup=rules_menu()
        )
        return
    
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 Панель администратора", reply_markup=admin_menu())
    else:
        await message.answer(
            "👋 Добро пожаловать в анонимный чат!\n🎁 У тебя есть бесплатный пробный доступ на 24 часа.",
            reply_markup=main_menu()
        )

@dp.message(Command("rules"))
async def rules_command(message: Message):
    await message.answer(RULES_TEXT, parse_mode='HTML', reply_markup=rules_menu())

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    await message.answer("🛠 Панель администратора", reply_markup=admin_menu())

@dp.message(Command("menu"))
async def menu_command(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 Панель администратора", reply_markup=admin_menu())
    else:
        await message.answer("📋 Главное меню", reply_markup=main_menu())

@dp.message(Command("report"))
async def report_command(message: Message):
    user_id = message.from_user.id
    if is_user_banned(user_id):
        await message.answer("🚫 Вы заблокированы и не можете отправлять жалобы.")
        return
    if user_id not in active_chats:
        await message.answer("❌ Вы не в активном чате. Нет на кого жаловаться.")
        return
    await message.answer("🚨 <b>Пожаловаться на собеседника</b>\n\nВыберите причину жалобы:", 
                        parse_mode='HTML', reply_markup=report_menu())

# ==========================
# 📜 СИСТЕМА ПРАВИЛ
# ==========================

@dp.callback_query(F.data == "read_rules")
async def read_rules_callback(callback: CallbackQuery):
    await callback.message.edit_text(RULES_TEXT, parse_mode='HTML', reply_markup=rules_menu())

@dp.callback_query(F.data == "accept_rules")
async def accept_rules_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    user["rules_accepted"] = True
    user["rules_accepted_date"] = datetime.now()
    
    await callback.message.edit_text("✅ <b>Правила приняты!</b>", parse_mode='HTML')
    await callback.message.answer("📋 Главное меню:", reply_markup=main_menu())

# ==========================
# 👤 РАСКРЫТИЕ USERNAME
# ==========================

@dp.message(lambda msg: msg.text == "👤 Показать username")
async def request_username(message: Message):
    user_id = message.from_user.id
    if user_id not in active_chats:
        await message.answer("❌ Вы не в активном чате.")
        return
    
    if not can_request_username(user_id):
        await message.answer("⏳ Вы можете запрашивать username не чаще чем раз в 10 минут.")
        return
    
    partner_id = active_chats[user_id]
    username_requests[user_id] = {"partner_id": partner_id, "timestamp": datetime.now()}
    
    user = get_user(user_id)
    user["username_requests_count"] += 1
    user["last_username_request"] = datetime.now()
    
    await bot.send_message(partner_id,
        "🔓 <b>Собеседник хочет раскрыть username!</b>\n\nЕсли вы согласны, оба username будут показаны друг другу.",
        parse_mode='HTML', reply_markup=username_request_menu())
    
    await message.answer("🔓 <b>Запрос на раскрытие username отправлен!</b>\n\nОжидаем согласия собеседника...", 
                        parse_mode='HTML')

@dp.callback_query(F.data == "accept_username")
async def accept_username_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    requester_id = None
    
    for uid, request in username_requests.items():
        if request["partner_id"] == user_id:
            requester_id = uid
            break
    
    if not requester_id:
        await callback.answer("❌ Запрос не найден")
        return
    
    try:
        requester = await bot.get_chat(requester_id)
        accepter = await bot.get_chat(user_id)
        
        requester_username = f"@{requester.username}" if requester.username else "❌ Username не установлен"
        accepter_username = f"@{accepter.username}" if accepter.username else "❌ Username не установлен"
        
        await callback.message.edit_text(
            f"✅ <b>Username раскрыты!</b>\n\n👤 <b>Ваш собеседник:</b> {requester_username}\n👤 <b>Ваш username:</b> {accepter_username}",
            parse_mode='HTML'
        )
        
        await bot.send_message(requester_id,
            f"✅ <b>Username раскрыты!</b>\n\n👤 <b>Ваш собеседник:</b> {accepter_username}\n👤 <b>Ваш username:</b> {requester_username}",
            parse_mode='HTML'
        )
        
        if requester_id in username_requests:
            del username_requests[requester_id]
            
    except Exception as e:
        await callback.message.edit_text("❌ Ошибка при получении username")

@dp.callback_query(F.data == "reject_username")
async def reject_username_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    requester_id = None
    
    for uid, request in username_requests.items():
        if request["partner_id"] == user_id:
            requester_id = uid
            break
    
    if requester_id:
        await bot.send_message(requester_id, "❌ Собеседник отклонил запрос на раскрытие username.")
        del username_requests[requester_id]
    
    await callback.message.edit_text("❌ Вы отклонили запрос на раскрытие username.")

# ==========================
# ⚙️ НАСТРОЙКИ И ПОЛ
# ==========================

@dp.message(lambda msg: msg.text == "⚙️ Настройки")
async def settings_command(message: Message):
    user = get_user(message.from_user.id)
    gender_text = get_gender_text(user['gender'])
    await message.answer(
        f"⚙️ <b>Настройки профиля</b>\n\n👤 <b>Твой пол:</b> {gender_text}\n📜 <b>Правила приняты:</b> {'✅' if user['rules_accepted'] else '❌'}",
        parse_mode='HTML', reply_markup=settings_menu()
    )

@dp.callback_query(F.data == "show_rules")
async def show_rules_callback(callback: CallbackQuery):
    await callback.message.edit_text(RULES_TEXT, parse_mode='HTML', reply_markup=rules_menu())

@dp.callback_query(F.data == "set_gender")
async def set_gender_callback(callback: CallbackQuery):
    await callback.message.edit_text("👤 <b>Выбери свой пол:</b>", parse_mode='HTML', reply_markup=gender_selection_menu())

@dp.callback_query(F.data.startswith("gender_"))
async def gender_selected(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    gender_map = {
        'gender_male': 'male',
        'gender_female': 'female', 
        'gender_none': None
    }
    selected_gender = gender_map[callback.data]
    user['gender'] = selected_gender
    gender_text = get_gender_text(selected_gender)
    await callback.message.edit_text(f"✅ <b>Пол успешно установлен!</b>\n\n👤 <b>Твой пол:</b> {gender_text}", parse_mode='HTML')

@dp.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    gender_text = get_gender_text(user['gender'])
    await callback.message.edit_text(
        f"⚙️ <b>Настройки профиля</b>\n\n👤 <b>Твой пол:</b> {gender_text}\n📜 <b>Правила приняты:</b> {'✅' if user['rules_accepted'] else '❌'}",
        parse_mode='HTML', reply_markup=settings_menu()
    )

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery):
    if callback.from_user.id == ADMIN_ID:
        await callback.message.edit_text("🛠 Панель администратора")
    else:
        await callback.message.answer("📋 Главное меню:", reply_markup=main_menu())

# ==========================
# 🔍 ПОИСК СОБЕСЕДНИКА
# ==========================

@dp.message(lambda msg: msg.text == "🔍 Найти собеседника")
async def search(message: Message):
    if is_user_banned(message.from_user.id):
        await message.answer("🚫 Вы заблокированы и не можете использовать бота.")
        return
    
    if not has_accepted_rules(message.from_user.id):
        await message.answer("❌ <b>Сначала необходимо принять правила!</b>\n\nИспользуйте команду /rules", parse_mode='HTML')
        return
    
    reset_daily_limits()
    user = get_user(message.from_user.id)

    if not has_active_subscription(user):
        if user["free_chats_today"] <= 0:
            return await message.answer("🚫 Лимит исчерпан. Купи подписку 💎")
        user["free_chats_today"] -= 1

    user_id = message.from_user.id

    if user_id in waiting_users:
        return await message.answer("⏳ Уже ищем...")

    if waiting_users:
        partner = waiting_users.pop()
        if is_user_banned(partner):
            await message.answer("❌ Найденный собеседник заблокирован. Продолжаем поиск...")
            waiting_users.add(user_id)
            return
            
        active_chats[user_id] = partner
        active_chats[partner] = user_id

        await bot.send_message(partner, "💬 Найден собеседник!", reply_markup=chat_menu())
        await message.answer("💬 Найден собеседник!", reply_markup=chat_menu())
    else:
        waiting_users.add(user_id)
        await message.answer("🔍 Идёт поиск...")

@dp.message(lambda msg: msg.text == "🔎 Поиск по полу")
async def search_by_gender(message: Message):
    if is_user_banned(message.from_user.id):
        await message.answer("🚫 Вы заблокированы и не можете использовать бота.")
        return
    
    if not has_accepted_rules(message.from_user.id):
        await message.answer("❌ <b>Сначала необходимо принять правила!</b>\n\nИспользуйте команду /rules", parse_mode='HTML')
        return
    
    reset_daily_limits()
    user = get_user(message.from_user.id)
    
    if not has_active_subscription(user):
        return await message.answer("🚫 <b>Поиск по полу доступен только с подпиской!</b>", parse_mode='HTML')

    user_id = message.from_user.id

    for gender_queue in waiting_users_by_gender.values():
        gender_queue.discard(user_id)

    await message.answer("🔎 <b>Поиск собеседника по полу</b>\n\n💎 <i>Эта функция доступна только с подпиской</i>", 
                        parse_mode='HTML', reply_markup=search_by_gender_menu())

@dp.callback_query(F.data.startswith("search_"))
async def search_gender_selected(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if not has_active_subscription(user):
        await callback.message.edit_text("🚫 <b>Поиск по полу доступен только с подпиской!</b>", parse_mode='HTML')
        return
    
    search_gender_map = {
        'search_male': 'male',
        'search_female': 'female',
        'search_any': 'any'
    }
    
    wanted_gender = search_gender_map[callback.data]
    user['search_gender'] = wanted_gender
    
    for gender_queue in waiting_users_by_gender.values():
        gender_queue.discard(user_id)
    
    if user.get('gender') is None and wanted_gender != 'any':
        await callback.message.edit_text("❌ <b>Сначала установи свой пол в настройках!</b>", parse_mode='HTML')
        return
    
    found_partner, found_gender = find_gender_partner(user_id, wanted_gender)
    
    if found_partner:
        active_chats[user_id] = found_partner
        active_chats[found_partner] = user_id
        
        for gender_queue in waiting_users_by_gender.values():
            gender_queue.discard(user_id)
            gender_queue.discard(found_partner)
        
        partner_user = get_user(found_partner)
        partner_gender_text = get_gender_text(partner_user.get('gender'))
        
        await callback.message.edit_text(f"💬 <b>Найден собеседник!</b>\n\n👤 Пол собеседника: {partner_gender_text}", parse_mode='HTML')
        
        user_gender_text = get_gender_text(user.get('gender'))
        await bot.send_message(found_partner, f"💬 <b>Найден собеседник!</b>\n\n👤 Пол собеседника: {user_gender_text}", parse_mode='HTML')
    else:
        waiting_users_by_gender[wanted_gender].add(user_id)
        user_gender_text = get_gender_text(user.get('gender'))
        search_text = get_search_gender_text(wanted_gender)
        await callback.message.edit_text(f"🔍 <b>Ищем {search_text.lower()}...</b>\n\n👤 Твой пол: {user_gender_text}", parse_mode='HTML')

@dp.message(lambda msg: msg.text == "❌ Остановить чат")
async def stop(message: Message):
    user_id = message.from_user.id

    if user_id in active_chats:
        partner = active_chats.pop(user_id)
        active_chats.pop(partner, None)
        await bot.send_message(partner, "❌ Собеседник отключился.", reply_markup=main_menu())
        await message.answer("❌ Чат завершён.", reply_markup=main_menu())
        return

    if user_id in waiting_users:
        waiting_users.remove(user_id)
        return await message.answer("❌ Поиск остановлен.")
    
    removed_from_gender = False
    for gender, queue in waiting_users_by_gender.items():
        if user_id in queue:
            queue.remove(user_id)
            removed_from_gender = True
    
    if removed_from_gender:
        return await message.answer("❌ Поиск по полу остановлен.")

    await message.answer("ℹ️ Вы не в чате.")

# ==========================
# 🚨 СИСТЕМА ЖАЛОБ
# ==========================

@dp.message(lambda msg: msg.text == "🚨 Пожаловаться")
async def report_button(message: Message):
    user_id = message.from_user.id
    if is_user_banned(user_id):
        await message.answer("🚫 Вы заблокированы и не можете отправлять жалобы.")
        return
    if user_id not in active_chats:
        await message.answer("❌ Вы не в активном чате. Нет на кого жаловаться.")
        return
    await message.answer("🚨 <b>Пожаловаться на собеседника</b>\n\nВыберите причину жалобы:", 
                        parse_mode='HTML', reply_markup=report_menu())

@dp.callback_query(F.data.startswith("report_"))
async def report_reason_selected(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in active_chats:
        await callback.message.edit_text("❌ Чат уже завершен.")
        return
    
    reported_user_id = active_chats[user_id]
    reason_map = {
        "report_insults": "Оскорбления",
        "report_content": "Неприемлемый контент", 
        "report_spam": "Спам/Реклама",
        "report_other": "Другое"
    }
    reason = reason_map[callback.data]
    report_id = create_report(user_id, reported_user_id, reason)
    partner = active_chats.pop(user_id)
    active_chats.pop(partner, None)
    
    await callback.message.edit_text(f"✅ <b>Жалоба отправлена!</b>\n\n🚨 Причина: {reason}\n📋 Номер жалобы: #{report_id}", parse_mode='HTML')
    await bot.send_message(partner, "❌ Собеседник отключился и отправил жалобу.\nЧат завершен.", reply_markup=main_menu())
    
    user_gender = get_gender_text(get_user(user_id).get('gender'))
    reported_gender = get_gender_text(get_user(reported_user_id).get('gender'))
    
    await bot.send_message(ADMIN_ID,
        f"🚨 <b>Новая жалоба #{report_id}</b>\n\n👤 <b>Жалобщик:</b> {user_id} ({user_gender})\n👤 <b>Нарушитель:</b> {reported_user_id} ({reported_gender})\n📋 <b>Причина:</b> {reason}",
        parse_mode='HTML', reply_markup=admin_report_menu(report_id)
    )

@dp.callback_query(F.data == "back_to_chat")
async def back_to_chat_callback(callback: CallbackQuery):
    await callback.message.edit_text("Возврат в чат...")

# ==========================
# 💎 Покупка подписки
# ==========================

@dp.message(lambda msg: msg.text == "💎 Купить подписку")
async def buy_sub(message: Message):
    await message.answer("🔥 Выбери подписку:", reply_markup=subscription_menu())

@dp.callback_query(lambda c: c.data.startswith("buy_") or c.data == "back")
async def subscription_choice(callback: types.CallbackQuery):
    if callback.data == "back":
        return await callback.message.edit_text("Меню:", reply_markup=main_menu())

    mapping = {
        "buy_1": (1, 5),
        "buy_7": (7, 35),
        "buy_30": (30, 150)
    }

    days, price = mapping[callback.data]

    prices = [LabeledPrice(label=f"Подписка на {days} дней", amount=price)]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Подписка",
        description=f"Доступ на {days} дней.",
        payload=str(days),
        provider_token="",
        currency="XTR",
        prices=prices
    )

@dp.pre_checkout_query()
async def process_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(lambda m: m.successful_payment)
async def success_payment(message: Message):
    days = int(message.successful_payment.invoice_payload)
    add_subscription(message.from_user.id, days)

    user = get_user(message.from_user.id)
    until = user["subscription_until"].strftime("%d.%m.%Y %H:%M")

    await message.answer(f"🎉 Подписка активирована до: {until}", reply_markup=main_menu())
    await bot.send_message(ADMIN_ID, f"💎 {message.from_user.id} купил подписку на {days} дней.")


# ==========================
# ℹ️ Проверка подписки
# ==========================

@dp.message(lambda msg: msg.text == "ℹ️ Моя подписка")
async def sub_info(message: Message):
    user = get_user(message.from_user.id)
    reset_daily_limits()
    if has_active_subscription(user):
        delta = user["subscription_until"] - datetime.now()
        days = delta.days
        hours = delta.seconds // 3600
        text = f"💎 <b>Подписка активна</b>\n\n⏳ Осталось: {days}д {hours}ч"
    else:
        text = f"🚫 <b>Подписка не активна</b>\n\n🎯 Бесплатных чатов сегодня: {user['free_chats_today']}/{FREE_CHAT_LIMIT}"
    await message.answer(text, parse_mode='HTML')

# ==========================
# 🛠 АДМИН ПАНЕЛЬ
# ==========================

@dp.message(F.text == "🚪 Выйти из админ-панели")
async def exit_admin_panel(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👋 Вы вышли из админ-панели.", reply_markup=main_menu())
    else:
        await message.answer("📋 Главное меню", reply_markup=main_menu())

@dp.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    active_chats_count = len(active_chats) // 2
    waiting_count = len(waiting_users)
    waiting_by_gender = {
        'male': len(waiting_users_by_gender['male']),
        'female': len(waiting_users_by_gender['female']),
        'any': len(waiting_users_by_gender['any'])
    }
    total_users = len(users)
    premium_users = sum(1 for user in users.values() if has_active_subscription(user))
    trial_users = sum(1 for user in users.values() if user.get("trial_given", False))
    male_users = sum(1 for user in users.values() if user.get('gender') == 'male')
    female_users = sum(1 for user in users.values() if user.get('gender') == 'female')
    unknown_gender = total_users - male_users - female_users
    
    stats_text = f"""📊 **Статистика бота:**

👥 **Пользователи:** {total_users}
💬 **Активность:**
   В чатах: {active_chats_count}
   В поиске: {waiting_count}
   По полу: 👨{waiting_by_gender['male']} 👩{waiting_by_gender['female']} 🤷{waiting_by_gender['any']}
💎 **Подписки:** Премиум: {premium_users}, Триал: {trial_users}"""
    await message.answer(stats_text)

@dp.message(F.text == "👥 Пользователи")
async def users_management(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    users_list = []
    for user_id, user_data in list(users.items())[:10]:
        status = "💎" if has_active_subscription(user_data) else "🆓"
        gender = get_gender_text(user_data.get('gender'))
        users_list.append(f"{status} ID: {user_id} | {gender}")
    
    text = "📋 Последние 10 пользователей:\n" + "\n".join(users_list)
    if len(users) > 10:
        text += f"\n\n... и еще {len(users) - 10} пользователей"
    await message.answer(text)

@dp.message(F.text == "📢 Рассылка")
async def broadcast_start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    broadcast_data[message.from_user.id] = {"state": "waiting_message"}
    await message.answer("📝 Отправьте сообщение для рассылки:")

@dp.message(lambda msg: msg.from_user.id in broadcast_data and broadcast_data[msg.from_user.id]["state"] == "waiting_message")
async def broadcast_message_received(message: Message):
    user_id = message.from_user.id
    broadcast_data[user_id] = {"state": "waiting_confirmation", "message_text": message.text}
    await message.answer(f"📨 Подтвердите рассылку:\n\n{message.text}", reply_markup=broadcast_confirmation())

@dp.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in broadcast_data:
        await callback.answer("❌ Данные рассылки утеряны")
        return
    data = broadcast_data[user_id]
    await callback.message.edit_text("🔄 Начинаю рассылку...")
    success = 0
    failed = 0
    for user_id in users.keys():
        try:
            await bot.send_message(user_id, data["message_text"])
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    del broadcast_data[user_id]
    await callback.message.edit_text(f"✅ Рассылка завершена:\n• Успешно: {success}\n• Не удалось: {failed}")

@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery):
    if callback.from_user.id in broadcast_data:
        del broadcast_data[callback.from_user.id]
    await callback.message.edit_text("❌ Рассылка отменена")

@dp.message(F.text == "⚙️ Управление подписками")
async def subscription_management(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("💎 Управление подписками:", reply_markup=subscription_management_menu())

@dp.callback_query(F.data == "admin_add_sub")
async def admin_add_subscription(callback: CallbackQuery):
    await callback.message.edit_text("➕ Добавление подписки\n\nИспользуйте: /add_sub user_id days")

@dp.callback_query(F.data == "admin_remove_sub")
async def admin_remove_subscription(callback: CallbackQuery):
    await callback.message.edit_text("❌ Снятие подписки\n\nИспользуйте: /remove_sub user_id")

@dp.callback_query(F.data == "admin_list_subs")
async def admin_list_subscriptions(callback: CallbackQuery):
    premium_users = []
    for user_id, user_data in users.items():
        if has_active_subscription(user_data):
            until = user_data["subscription_until"].strftime("%d.%m.%Y")
            days_left = (user_data["subscription_until"] - datetime.now()).days
            premium_users.append(f"👤 {user_id} | до {until} | {days_left}д")
    if premium_users:
        text = "💎 Пользователи с подпиской:\n" + "\n".join(premium_users[:10])
    else:
        text = "❌ Нет пользователей с подпиской"
    await callback.message.edit_text(text)

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.edit_text("🛠 Панель администратора")

@dp.message(F.text == "🚨 Жалобы")
async def admin_reports(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    new_reports = [r for r in reports.values() if r["status"] == "new"]
    if not new_reports:
        await message.answer("✅ Нет новых жалоб.")
        return
    report_id = next(iter(reports))
    await show_report(message, report_id)

async def show_report(message, report_id):
    if report_id not in reports:
        await message.answer("❌ Жалоба не найдена.")
        return
    report = reports[report_id]
    user = get_user(report["user_id"])
    reported_user = get_user(report["reported_user_id"])
    text = f"🚨 Жалоба #{report_id}\n👤 Жалобщик: {report['user_id']}\n👤 Нарушитель: {report['reported_user_id']}\n📋 Причина: {report['reason']}"
    await message.answer(text, reply_markup=admin_report_menu(report_id))

@dp.callback_query(F.data.startswith("view_chat_"))
async def view_chat_history(callback: CallbackQuery):
    report_id = int(callback.data.split("_")[2])
    if report_id not in reports:
        await callback.answer("❌ Жалоба не найдена")
        return
    report = reports[report_id]
    chat_history = report["chat_history"]
    if not chat_history:
        await callback.message.answer("📝 История чата пуста.")
        return
    history_text = "📝 История чата:\n"
    for msg in chat_history[-5:]:
        user_prefix = "👤" if msg["user"] == report["user_id"] else "🚨"
        history_text += f"{user_prefix}: {msg['text']}\n"
    await callback.message.answer(history_text)

@dp.callback_query(F.data.startswith("ban_both_"))
async def ban_both_users(callback: CallbackQuery):
    report_id = int(callback.data.split("_")[2])
    if report_id not in reports:
        await callback.answer("❌ Жалоба не найдена")
        return
    report = reports[report_id]
    user_id = report["user_id"]
    reported_id = report["reported_user_id"]
    banned_users.add(user_id)
    banned_users.add(reported_id)
    reports[report_id]["status"] = "resolved"
    await callback.message.edit_text(f"✅ Оба пользователя заблокированы")

@dp.callback_query(F.data.startswith("ban_reporter_"))
async def ban_reporter(callback: CallbackQuery):
    report_id = int(callback.data.split("_")[2])
    if report_id not in reports:
        await callback.answer("❌ Жалоба не найдена")
        return
    report = reports[report_id]
    user_id = report["user_id"]
    banned_users.add(user_id)
    reports[report_id]["status"] = "resolved"
    await callback.message.edit_text(f"✅ Жалобщик {user_id} заблокирован")

@dp.callback_query(F.data.startswith("ban_reported_"))
async def ban_reported(callback: CallbackQuery):
    report_id = int(callback.data.split("_")[2])
    if report_id not in reports:
        await callback.answer("❌ Жалоба не найдена")
        return
    report = reports[report_id]
    reported_id = report["reported_user_id"]
    banned_users.add(reported_id)
    reports[report_id]["status"] = "resolved"
    await callback.message.edit_text(f"✅ Нарушитель {reported_id} заблокирован")

@dp.callback_query(F.data.startswith("reject_report_"))
async def reject_report(callback: CallbackQuery):
    report_id = int(callback.data.split("_")[2])
    if report_id not in reports:
        await callback.answer("❌ Жалоба не найдена")
        return
    reports[report_id]["status"] = "rejected"
    await callback.message.edit_text(f"✅ Жалоба #{report_id} отклонена")

@dp.callback_query(F.data == "next_report")
async def next_report(callback: CallbackQuery):
    new_reports = [r for r in reports.values() if r["status"] == "new"]
    if not new_reports:
        await callback.message.edit_text("✅ Нет новых жалоб.")
        return
    current_report_id = next(iter(reports))
    await show_report(callback.message, current_report_id)

@dp.message(F.text == "🚫 Заблокированные")
async def banned_users_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not banned_users:
        await message.answer("✅ Нет заблокированных пользователей.")
        return
    banned_list = "🚫 Заблокированные:\n" + "\n".join([f"👤 {user_id}" for user_id in list(banned_users)[:10]])
    await message.answer(banned_list)

# ==========================
# 🎯 КОМАНДЫ УПРАВЛЕНИЯ
# ==========================

@dp.message(Command("add_sub"))
async def add_subscription_command(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    if not command.args:
        await message.answer("❌ Использование: /add_sub user_id days")
        return
    try:
        args = command.args.split()
        user_id = int(args[0])
        days = int(args[1])
        add_subscription(user_id, days)
        user = get_user(user_id)
        until = user["subscription_until"].strftime("%d.%m.%Y %H:%M")
        await message.answer(f"✅ Пользователю {user_id} добавлено {days} дней подписки\nДо: {until}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("remove_sub"))
async def remove_subscription_command(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    if not command.args:
        await message.answer("❌ Использование: /remove_sub user_id")
        return
    try:
        user_id = int(command.args)
        user = get_user(user_id)
        user["subscription_until"] = datetime.now() - timedelta(days=1)
        await message.answer(f"✅ Подписка пользователя {user_id} отменена")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("user_info"))
async def user_info_command(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    if not command.args:
        await message.answer("❌ Использование: /user_info user_id")
        return
    try:
        user_id = int(command.args)
        user = get_user(user_id)
        status = "💎" if has_active_subscription(user) else "🆓"
        gender = get_gender_text(user.get('gender'))
        info_text = f"👤 ID: {user_id}\nСтатус: {status}\nПол: {gender}"
        await message.answer(info_text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("broadcast"))
async def broadcast_command(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    if not command.args:
        await message.answer("❌ Использование: /broadcast ваш_текст")
        return
    broadcast_data[message.from_user.id] = {"state": "waiting_confirmation", "message_text": command.args}
    await message.answer(f"📨 Подтвердите рассылку:\n\n{command.args}", reply_markup=broadcast_confirmation())

# ==========================
# 📡 Relay Chat
# ==========================

@dp.message()
async def relay(message: Message):
    user_id = message.from_user.id
    if is_user_banned(user_id):
        await message.answer("🚫 Вы заблокированы.")
        return
    if user_id in active_chats:
        partner = active_chats[user_id]
        if is_user_banned(partner):
            await message.answer("❌ Собеседник заблокирован.")
            active_chats.pop(user_id)
            return
        add_to_chat_history(user_id, message.text)
        add_to_chat_history(partner, message.text)
        await bot.send_message(partner, message.text)


# ==========================
# ▶ RUN
# ==========================

def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    if WEBHOOK_URL:
        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        return app

if __name__ == "__main__":
    if WEBHOOK_URL:
        app = main()
        web.run_app(app, host="0.0.0.0", port=10000)
    else:
        asyncio.run(dp.start_polling(bot))
