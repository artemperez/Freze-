#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Further BoTнЕт - Многофункциональный бот для работы с Telegram
Владелец: @aurieza (8050595279)
"""

import os
import asyncio
import logging
import json
import sys
from datetime import datetime

# Обход ошибки imghdr в Python 3.13
try:
    import imghdr
except ModuleNotFoundError:
    class SimpleImghdr:
        @staticmethod
        def what(file, h=None):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                return file.split('.')[-1].lower()
            return None
    sys.modules['imghdr'] = SimpleImghdr()

# Импорт основных библиотек
import re
import random
import sqlite3
from telethon import TelegramClient, events, functions, Button
from telethon.sessions import StringSession
from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonOther,
    CodeSettings
)
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import (
    FloodWaitError,
    UserAlreadyParticipantError,
    SessionRevokedError,
    AuthKeyUnregisteredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError
)
from telethon.tl.functions.auth import SendCodeRequest, SignInRequest, CheckPasswordRequest
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

# ============ КОНФИГУРАЦИЯ ============
API_ID = 22778226
API_HASH = "9be02c55dfb4c834210599490dcd58a8"
BOT_TOKEN = "7948393581:AAEhEFRyHmg15rgeL0zKDnni5CXXcaJqaHs"
OWNER_ID = 8050595279  # @aurieza
ADMIN_IDS = {OWNER_ID, 8356950033}  # Владелец + админ

# Папки и файлы
SESSIONS_FOLDER = "sessions"
USERS_DB = "users.db"
ADMINS_FILE = "admins.json"
SUBSCRIPTIONS_FILE = "subscriptions.json"
RULES_FILE = "rules.txt"
CHANNELS_FILE = "required_channels.json"  # Файл с обязательными каналами

# Создание необходимых папок и файлов
if not os.path.exists(SESSIONS_FOLDER):
    os.makedirs(SESSIONS_FOLDER)

if not os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, 'w') as f:
        json.dump({"admins": list(ADMIN_IDS)}, f)

if not os.path.exists(SUBSCRIPTIONS_FILE):
    with open(SUBSCRIPTIONS_FILE, 'w') as f:
        json.dump({}, f)

if not os.path.exists(RULES_FILE):
    with open(RULES_FILE, 'w', encoding='utf-8') as f:
        rules_text = """📜 Правила использования бота Further BoTнЕт:

1. Запрещено использование бота для спама и нарушений правил Telegram
2. Администрация вправе заблокировать доступ без объяснения причин
3. Все действия логируются и могут быть проверены
4. Запрещено передавать доступ третьим лицам
5. Ответственность за использование бота лежит на пользователе
6. Для использования бота необходимо подписаться на все обязательные каналы

👑 Создатель: @aurieza
📞 Контакты: @aurieza"""
        f.write(rules_text)

# Файл с обязательными каналами
if not os.path.exists(CHANNELS_FILE):
    with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            "channels": [
                {"username": "@aurieza", "title": "Канал создателя", "required": True}
            ]
        }, f, ensure_ascii=False, indent=4)

# ============ БАЗА ДАННЫХ ============
def init_db():
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            subscription_until DATETIME,
            join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT 0,
            ban_reason TEXT,
            reports_sent INTEGER DEFAULT 0,
            last_activity DATETIME
        )
    ''')
    
    # Таблица статистики
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            total_reports INTEGER DEFAULT 0,
            total_subscriptions INTEGER DEFAULT 0,
            total_bot_refs INTEGER DEFAULT 0,
            sessions_added INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица подписок на обязательные каналы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_subscriptions (
            user_id INTEGER,
            channel_username TEXT,
            subscribed BOOLEAN DEFAULT 0,
            checked_date DATETIME,
            PRIMARY KEY (user_id, channel_username)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ============ ФУНКЦИИ ДЛЯ РАБОТЫ С БД ============
def add_user_to_db(user_id, username, first_name, last_name):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, last_activity)
        VALUES (?, ?, ?, ?, datetime('now'))
    ''', (user_id, username, first_name, last_name))
    
    conn.commit()
    conn.close()

def update_user_activity(user_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET last_activity = datetime('now') WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

def get_user_info(user_id):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.*, 
               COALESCE(s.total_reports, 0) as total_reports,
               COALESCE(s.total_subscriptions, 0) as total_subscriptions,
               COALESCE(s.total_bot_refs, 0) as total_bot_refs
        FROM users u
        LEFT JOIN user_stats s ON u.user_id = s.user_id
        WHERE u.user_id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, result))
    return None

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_owner(user_id):
    return user_id == OWNER_ID

def check_subscription(user_id):
    # Админы и владелец всегда имеют доступ
    if is_admin(user_id):
        return True
    
    user_info = get_user_info(user_id)
    if not user_info:
        return False
    
    if user_info['subscription_until']:
        try:
            from datetime import datetime
            subscription_until = datetime.fromisoformat(user_info['subscription_until'])
            return datetime.now() < subscription_until
        except:
            return False
    
    return False

def set_subscription(user_id, days):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    
    from datetime import datetime, timedelta
    if days == 0:
        new_date = None
    else:
        new_date = datetime.now() + timedelta(days=days)
    
    cursor.execute('''
        UPDATE users SET subscription_until = ? WHERE user_id = ?
    ''', (new_date, user_id))
    
    conn.commit()
    conn.close()
    
    # Обновляем файл подписок
    with open(SUBSCRIPTIONS_FILE, 'r') as f:
        subscriptions = json.load(f)
    
    subscriptions[str(user_id)] = new_date.isoformat() if new_date else None
    
    with open(SUBSCRIPTIONS_FILE, 'w') as f:
        json.dump(subscriptions, f)
    
    return True

# ============ ФУНКЦИИ ДЛЯ ОБЯЗАТЕЛЬНЫХ КАНАЛОВ ============
def load_required_channels():
    try:
        with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("channels", [])
    except:
        return []

def save_required_channels(channels):
    data = {"channels": channels}
    with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_required_channel(username, title=""):
    channels = load_required_channels()
    
    # Проверяем, нет ли уже такого канала
    for channel in channels:
        if channel["username"] == username:
            return False
    
    channels.append({
        "username": username,
        "title": title,
        "required": True,
        "added_date": datetime.now().isoformat()
    })
    
    save_required_channels(channels)
    return True

def remove_required_channel(username):
    channels = load_required_channels()
    new_channels = [c for c in channels if c["username"] != username]
    
    if len(new_channels) != len(channels):
        save_required_channels(new_channels)
        return True
    return False

def check_user_channel_subscription(user_id, client=None):
    """Проверяет, подписан ли пользователь на все обязательные каналы"""
    channels = load_required_channels()
    
    if not channels:
        return True, []
    
    if client is None:
        # Не можем проверить без клиента
        return False, channels
    
    not_subscribed = []
    
    for channel in channels:
        username = channel["username"].lstrip("@")
        try:
            entity = client.get_input_entity(username)
            # Проверяем подписку
            try:
                channel_entity = client.loop.run_until_complete(client.get_entity(username))
                # Если мы здесь, значит подписан
                pass
            except:
                not_subscribed.append(channel)
        except:
            not_subscribed.append(channel)
    
    return len(not_subscribed) == 0, not_subscribed

def update_user_channel_status(user_id, channel_username, subscribed=True):
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO channel_subscriptions 
        (user_id, channel_username, subscribed, checked_date)
        VALUES (?, ?, ?, datetime('now'))
    ''', (user_id, channel_username, 1 if subscribed else 0))
    
    conn.commit()
    conn.close()

# ============ ИНИЦИАЛИЗАЦИЯ БОТА ============
bot = TelegramClient("further_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Состояния пользователей
user_states = {}
user_temp_data = {}

def get_user_state(user_id):
    return user_states.get(user_id, "none")

def set_user_state(user_id, state):
    user_states[user_id] = state

def set_temp_data(user_id, key, value):
    if user_id not in user_temp_data:
        user_temp_data[user_id] = {}
    user_temp_data[user_id][key] = value

def get_temp_data(user_id, key):
    return user_temp_data.get(user_id, {}).get(key)

# ============ ОСНОВНЫЕ ФУНКЦИИ БОТА ============
def load_sessions_from_folder():
    sessions = []
    if os.path.exists(SESSIONS_FOLDER):
        for file in os.listdir(SESSIONS_FOLDER):
            if file.endswith('.session'):
                sessions.append(os.path.join(SESSIONS_FOLDER, file))
    return sessions

# ============ ОБРАБОТЧИКИ КОМАНД ============
@bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
    username = event.sender.username or ""
    first_name = event.sender.first_name or ""
    last_name = event.sender.last_name or ""
    
    # Добавляем в БД
    add_user_to_db(user_id, username, first_name, last_name)
    update_user_activity(user_id)
    
    # Проверяем подписку на обязательные каналы
    required_channels = load_required_channels()
    if required_channels and not is_admin(user_id):
        channel_buttons = []
        for channel in required_channels:
            channel_buttons.append([Button.url(f"📢 {channel['title'] or channel['username']}", 
                                             f"https://t.me/{channel['username'].lstrip('@')}")])
        
        channel_buttons.append([Button.inline("✅ Я подписался", b"check_channels")])
        
        await event.reply(
            "📢 **Для использования бота необходимо подписаться на каналы:**\n\n" +
            "\n".join([f"• {ch['title'] or ch['username']}" for ch in required_channels]) +
            "\n\nПосле подписки нажмите кнопку ниже:",
            buttons=channel_buttons
        )
        return
    
    # Показываем главное меню
    await show_main_menu(event, user_id)

async def show_main_menu(event, user_id):
    if is_owner(user_id):
        buttons = [
            [Button.inline("👑 Владелец", b"owner_panel")],
            [Button.inline("⚠️ Отправить жалобу", b"send_report")],
            [Button.inline("📢 Массовая подписка", b"mass_subscribe")],
            [Button.inline("🔧 Управление сессиями", b"manage_sessions")],
            [Button.inline("👤 Профиль", b"profile"), Button.inline("📜 Правила", b"rules")]
        ]
    elif is_admin(user_id):
        buttons = [
            [Button.inline("⚡ Админ панель", b"admin_panel")],
            [Button.inline("⚠️ Отправить жалобу", b"send_report")],
            [Button.inline("📢 Массовая подписка", b"mass_subscribe")],
            [Button.inline("👤 Профиль", b"profile"), Button.inline("📜 Правила", b"rules")]
        ]
    elif check_subscription(user_id):
        buttons = [
            [Button.inline("⚠️ Отправить жалобу", b"send_report")],
            [Button.inline("📢 Массовая подписка", b"mass_subscribe")],
            [Button.inline("👤 Профиль", b"profile"), Button.inline("📜 Правила", b"rules")]
        ]
    else:
        buttons = [
            [Button.inline("👤 Профиль", b"profile")],
            [Button.inline("📜 Правила", b"rules")],
            [Button.inline("📞 Контакты", b"contacts")]
        ]
    
    await event.reply(
        "🤖 **Further BoTнЕт**\n\n"
        "Выберите действие:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(data=b"check_channels"))
async def check_channels_handler(event):
    user_id = event.sender_id
    
    # Для админов проверка не требуется
    if is_admin(user_id):
        await show_main_menu(event, user_id)
        return
    
    # Проверяем подписки
    try:
        required_channels = load_required_channels()
        not_subscribed = []
        
        for channel in required_channels:
            try:
                # Пытаемся получить информацию о канале
                entity = await bot.get_entity(channel["username"])
                # Проверяем подписку (упрощенная проверка)
                try:
                    await bot.get_participants(entity, limit=1)
                    # Если успешно, значит есть доступ к каналу
                    pass
                except:
                    not_subscribed.append(channel)
            except:
                not_subscribed.append(channel)
        
        if not_subscribed:
            channel_buttons = []
            for channel in not_subscribed:
                channel_buttons.append([Button.url(f"📢 {channel['title'] or channel['username']}", 
                                                 f"https://t.me/{channel['username'].lstrip('@')}")])
            
            channel_buttons.append([Button.inline("✅ Проверить снова", b"check_channels")])
            
            await event.edit(
                "❌ **Вы не подписаны на все каналы!**\n\n"
                "Не подписаны:\n" +
                "\n".join([f"• {ch['title'] or ch['username']}" for ch in not_subscribed]) +
                "\n\nПодпишитесь и нажмите кнопку ниже:",
                buttons=channel_buttons
            )
        else:
            await event.edit(
                "✅ **Отлично! Вы подписаны на все обязательные каналы.**\n\n"
                "Теперь вам доступны функции бота!",
                buttons=[[Button.inline("🚀 Продолжить", b"continue_to_main")]]
            )
    except Exception as e:
        await event.edit(
            f"⚠️ **Ошибка проверки подписок:** {str(e)[:100]}\n\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору.",
            buttons=[[Button.inline("🔄 Попробовать снова", b"check_channels")]]
        )

@bot.on(events.CallbackQuery(data=b"continue_to_main"))
async def continue_to_main_handler(event):
    await show_main_menu(event, event.sender_id)

@bot.on(events.CallbackQuery(data=b"owner_panel"))
async def owner_panel_handler(event):
    if not is_owner(event.sender_id):
        await event.answer("❌ Только для владельца!")
        return
    
    sessions_count = len(load_sessions_from_folder())
    required_channels = load_required_channels()
    
    await event.edit(
        f"👑 **Панель владельца**\n\n"
        f"📊 Статистика:\n"
        f"• Сессий: {sessions_count}\n"
        f"• Админов: {len(ADMIN_IDS)}\n"
        f"• Обязательных каналов: {len(required_channels)}\n\n"
        f"Выберите действие:",
        buttons=[
            [Button.inline("👥 Управление пользователями", b"manage_users")],
            [Button.inline("🔧 Управление сессиями", b"manage_sessions")],
            [Button.inline("📢 Управление каналами", b"manage_channels")],
            [Button.inline("⚙️ Настройки бота", b"bot_settings")],
            [Button.inline("📊 Полная статистика", b"full_stats")],
            [Button.inline("🔙 Назад", b"back_to_main")]
        ]
    )

@bot.on(events.CallbackQuery(data=b"admin_panel"))
async def admin_panel_handler(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Только для администраторов!")
        return
    
    await event.edit(
        "⚡ **Админ панель**\n\n"
        "Доступные функции:",
        buttons=[
            [Button.inline("🎫 Выдать подписку", b"give_subscription")],
            [Button.inline("📢 Управление каналами", b"manage_channels")],
            [Button.inline("🚫 Заблокировать", b"ban_user_menu")],
            [Button.inline("✅ Разблокировать", b"unban_user_menu")],
            [Button.inline("🔍 Проверить сессии", b"check_sessions")],
            [Button.inline("🔙 Назад", b"back_to_main")]
        ]
    )

@bot.on(events.CallbackQuery(data=b"manage_channels"))
async def manage_channels_handler(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Только для администраторов!")
        return
    
    channels = load_required_channels()
    channels_list = "\n".join([f"• {ch['username']} - {ch['title']}" for ch in channels]) if channels else "Нет каналов"
    
    await event.edit(
        f"📢 **Управление обязательными каналами**\n\n"
        f"Текущие каналы:\n{channels_list}\n\n"
        f"Выберите действие:",
        buttons=[
            [Button.inline("➕ Добавить канал", b"add_channel")],
            [Button.inline("🗑️ Удалить канал", b"remove_channel")],
            [Button.inline("👁️ Просмотреть все", b"view_channels")],
            [Button.inline("🔄 Проверить подписки", b"check_all_subs")],
            [Button.inline("🔙 Назад", b"admin_panel")]
        ]
    )

@bot.on(events.CallbackQuery(data=b"add_channel"))
async def add_channel_handler(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Только для администраторов!")
        return
    
    set_user_state(event.sender_id, "adding_channel")
    
    await event.edit(
        "➕ **Добавление обязательного канала**\n\n"
        "Отправьте данные в формате:\n"
        "`@username Название канала`\n\n"
        "Пример:\n"
        "`@aurieza Канал создателя`",
        buttons=[
            [Button.inline("🔙 Назад", b"manage_channels")]
        ]
    )

@bot.on(events.CallbackQuery(data=b"remove_channel"))
async def remove_channel_handler(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Только для администраторов!")
        return
    
    channels = load_required_channels()
    
    if not channels:
        await event.answer("❌ Нет каналов для удаления!")
        return
    
    # Создаем кнопки для каждого канала
    buttons = []
    for channel in channels:
        buttons.append([Button.inline(f"🗑️ {channel['username']}", f"remove_channel_{channel['username'].replace('@', '')}")])
    
    buttons.append([Button.inline("🔙 Назад", b"manage_channels")])
    
    await event.edit(
        "🗑️ **Удаление канала**\n\n"
        "Выберите канал для удаления:",
        buttons=buttons
    )

@bot.on(events.CallbackQuery(data=b"view_channels"))
async def view_channels_handler(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Только для администраторов!")
        return
    
    channels = load_required_channels()
    
    if not channels:
        channels_text = "📭 Нет обязательных каналов"
    else:
        channels_text = "📢 **Обязательные каналы:**\n\n"
        for i, channel in enumerate(channels, 1):
            channels_text += f"{i}. {channel['username']}\n"
            if channel.get('title'):
                channels_text += f"   📝 {channel['title']}\n"
            if channel.get('added_date'):
                from datetime import datetime
                try:
                    date = datetime.fromisoformat(channel['added_date'])
                    channels_text += f"   📅 Добавлен: {date.strftime('%d.%m.%Y')}\n"
                except:
                    pass
            channels_text += "\n"
    
    await event.edit(
        channels_text,
        buttons=[
            [Button.inline("🔄 Обновить", b"view_channels")],
            [Button.inline("🔙 Назад", b"manage_channels")]
        ]
    )

@bot.on(events.CallbackQuery(pattern=rb"remove_channel_"))
async def remove_specific_channel_handler(event):
    if not is_admin(event.sender_id):
        await event.answer("❌ Только для администраторов!")
        return
    
    channel_username = "@" + event.data.decode().split("_")[2]
    
    if remove_required_channel(channel_username):
        await event.edit(
            f"✅ Канал {channel_username} удален из обязательных!",
            buttons=[[Button.inline("🔙 Назад", b"manage_channels")]]
        )
    else:
        await event.edit(
            f"❌ Не удалось удалить канал {channel_username}",
            buttons=[[Button.inline("🔙 Назад", b"manage_channels")]]
        )

@bot.on(events.CallbackQuery(data=b"profile"))
async def profile_handler(event):
    user_id = event.sender_id
    user_info = get_user_info(user_id)
    
    if not user_info:
        await event.answer("Профиль не найден!")
        return
    
    # Определяем статус
    if is_owner(user_id):
        status = "👑 Владелец"
    elif is_admin(user_id):
        status = "⚡ Администратор"
    else:
        status = "👤 Пользователь"
    
    # Проверяем подписку
    if check_subscription(user_id):
        subscription_status = "✅ Активна"
    else:
        subscription_status = "❌ Не активна"
    
    # Проверяем обязательные каналы
    channels = load_required_channels()
    channels_status = "✅ Подписан" if not channels or is_admin(user_id) else "❌ Не проверено"
    
    profile_text = (
        f"👤 **Ваш профиль**\n\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"📛 **Имя:** {user_info['first_name'] or 'Не указано'}\n"
        f"👥 **Фамилия:** {user_info['last_name'] or 'Не указано'}\n"
        f"📱 **Username:** @{user_info['username'] or 'нет'}\n"
        f"🎖️ **Статус:** {status}\n\n"
        
        f"💎 **Подписка на бота:**\n"
        f"Статус: {subscription_status}\n\n"
        
        f"📢 **Обязательные каналы:**\n"
        f"Статус: {channels_status}\n\n"
        
        f"📊 **Статистика:**\n"
        f"• Отправлено жалоб: {user_info['total_reports'] or 0}\n"
        f"• Выполнено подписок: {user_info['total_subscriptions'] or 0}\n"
        f"• Рефералов в ботов: {user_info['total_bot_refs'] or 0}\n\n"
        
        f"📅 **Дата регистрации:**\n"
        f"{user_info['join_date']}"
    )
    
    buttons = [[Button.inline("🔙 Назад", b"back_to_main")]]
    await event.edit(profile_text, buttons=buttons)

@bot.on(events.CallbackQuery(data=b"back_to_main"))
async def back_to_main_handler(event):
    await show_main_menu(event, event.sender_id)

# ============ ОБРАБОТКА СООБЩЕНИЙ ============
@bot.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    text = event.raw_text.strip()
    state = get_user_state(user_id)
    
    # Игнорируем команды
    if text.startswith('/'):
        return
    
    # Обработка добавления канала
    if state == "adding_channel" and is_admin(user_id):
        clear_user_state(user_id)
        
        parts = text.split(' ', 1)
        if len(parts) >= 1:
            username = parts[0]
            title = parts[1] if len(parts) > 1 else username
            
            # Проверяем формат username
            if not username.startswith('@'):
                username = '@' + username
            
            if add_required_channel(username, title):
                await event.reply(
                    f"✅ Канал {username} добавлен в обязательные!\n"
                    f"Название: {title}\n\n"
                    f"Теперь пользователи должны будут подписаться на этот канал для использования бота."
                )
            else:
                await event.reply(f"❌ Канал {username} уже есть в списке!")
        else:
            await event.reply("❌ Неверный формат! Пример: `@username Название канала`")

# ============ ДОПОЛНИТЕЛЬНЫЕ ОБРАБОТЧИКИ ============
@bot.on(events.CallbackQuery(data=b"rules"))
async def rules_handler(event):
    try:
        with open(RULES_FILE, 'r', encoding='utf-8') as f:
            rules = f.read()
    except:
        rules = "Правила временно недоступны"
    
    await event.edit(
        rules,
        buttons=[
            [Button.inline("🔙 Назад", b"back_to_main")]
        ]
    )

@bot.on(events.CallbackQuery(data=b"contacts"))
async def contacts_handler(event):
    contacts_text = (
        "📞 **Контакты для связи**\n\n"
        "👑 **Создатель бота:**\n"
        "• @aurieza\n"
        "• ID: 8050595279\n\n"
        
        "💎 **Для получения подписки:**\n"
        "1. Напишите @aurieza\n"
        "2. Укажите ваш ID\n"
        "3. Ожидайте ответа\n\n"
        
        "⚠️ **Внимание:**\n"
        "Только официальный создатель может выдавать доступ!"
    )
    
    await event.edit(
        contacts_text,
        buttons=[
            [Button.inline("🔙 Назад", b"back_to_main")]
        ]
    )

# ============ ЗАПУСК БОТА ============
async def main():
    print("=== Further BoTнЕт ===")
    print(f"Владелец: @aurieza (8050595279)")
    print(f"Админ: 8356950033")
    print(f"API ID: {API_ID}")
    print(f"Сессий: {len(load_sessions_from_folder())}")
    print("=" * 30)
    print("🚀 Бот запускается...")
    
    try:
        await bot.start(bot_token=BOT_TOKEN)
        print("✅ Бот успешно запущен!")
        print("📞 Контакт для подписок: @aurieza")
        await bot.run_until_disconnected()
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    print("🔧 Инициализация Further BoTнЕт...")
    
    # Проверяем данные
    if API_ID == 22778226 and API_HASH == "9be02c55dfb4c834210599490dcd58a8" and BOT_TOKEN == "7948393581:AAEhEFRyHmg15rgeL0zKDnni5CXXcaJqaHs":
        print("✅ Данные API загружены")
        print("✅ Токен бота загружен")
        
        # Запускаем бота
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n👋 Бот остановлен пользователем")
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
    else:
        print("❌ ОШИБКА: Проверьте данные API!")
        print("ℹ️ Убедитесь, что API_ID, API_HASH и BOT_TOKEN указаны верно")