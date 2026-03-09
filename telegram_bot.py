# telegram_bot.py
import random

import requests
import telebot
from telebot.types import InputMediaPhoto

from database import Database
from config import TELEGRAM_TOKEN, DISCORD_WEBHOOK_URL, PARTICIPANTS
from pubg_api import (
    build_gun_list_text_and_aliases,
    build_random_loadout,
    format_suggestions_text,
    format_weapon_details_text,
    get_weapon_details_by_url,
    resolve_weapon_url,
)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
db = Database()


def send_to_discord(text, discord_id):
    data = {
        "content": f"<@{discord_id}>",
        "embeds": [
            {
                "title": "Ты...",
                "description": text,
                "color": 16645629,
                "footer": {
                    "text": "Ответь на это сообщение, чтобы ответить обидчику"
                },
            }
        ],
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=data,
            params={"wait": "true"},
            timeout=10,
        )
        if response.status_code == 200:
            webhook_response = response.json()
            return webhook_response.get("id")

        print(f"❌ Ошибка отправки в Discord: {response.status_code} - {response.text}")
        return None
    except Exception as e:
        print(f"❌ Ошибка соединения с Discord: {e}")
        return None


@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.reply_to(
        message,
        "Я бот Соль, достану твоих друзей в дискорде. Напиши оскорбление и пусть всё решит удача.\n\n"
        "В групповых чатах упомяни меня: @salt_tg_ds_bot лох",
    )


@bot.message_handler(commands=["gun"])
def handle_gun(message):
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)

    try:
        # /gun -> список оружия.
        if len(parts) == 1:
            guns_text, aliases = build_gun_list_text_and_aliases()
            if aliases:
                db.upsert_weapon_aliases(aliases)
            bot.reply_to(message, guns_text)
            return

        # /gun <gun_name> -> карточка конкретного оружия.
        query = parts[1]
        if query.lower() == "random":
            main_weapons, optional_pistol = build_random_loadout()
            summary = (
                "Случайный набор:\n"
                f"1) {main_weapons[0]['name']}\n"
                f"2) {main_weapons[1]['name']}\n"
                f"Опционально (пистолет): {optional_pistol['name']}"
            )
            bot.reply_to(message, summary)
            media = [
                InputMediaPhoto(main_weapons[0]["image"], caption=f"1) {main_weapons[0]['name']}"),
                InputMediaPhoto(main_weapons[1]["image"], caption=f"2) {main_weapons[1]['name']}"),
                InputMediaPhoto(
                    optional_pistol["image"],
                    caption=f"Опционально (пистолет): {optional_pistol['name']}",
                ),
            ]
            bot.send_media_group(chat_id=message.chat.id, media=media, reply_to_message_id=message.message_id)
            return

        weapon_url, suggestions = resolve_weapon_url(query, db)
        if not weapon_url:
            _, aliases = build_gun_list_text_and_aliases()
            if aliases:
                db.upsert_weapon_aliases(aliases)
            weapon_url, suggestions = resolve_weapon_url(query, db)

        if not weapon_url:
            bot.reply_to(
                message,
                "❌ Оружие не найдено." + format_suggestions_text(suggestions),
            )
            return

        details = get_weapon_details_by_url(weapon_url)
        caption = format_weapon_details_text(details)
        image_url = details.get("image")

        if image_url:
            bot.send_photo(
                chat_id=message.chat.id,
                photo=image_url,
                caption=caption,
                reply_to_message_id=message.message_id,
            )
        else:
            bot.reply_to(message, caption)
    except Exception as e:
        print(f"❌ Ошибка /gun (Telegram): {e}")
        bot.reply_to(message, "❌ Не удалось получить данные по оружию.")


def is_bot_mentioned(message):
    text = message.text or message.caption or ""
    if not text:
        return False

    me = bot.get_me()
    bot_username = f"@{me.username}".lower()
    if bot_username in text.lower():
        return True

    entities = []
    if getattr(message, "entities", None):
        entities.extend(message.entities)
    if getattr(message, "caption_entities", None):
        entities.extend(message.caption_entities)

    for entity in entities:
        if entity.type == "mention":
            mention = text[entity.offset : entity.offset + entity.length].lower()
            if mention == bot_username:
                return True
        if entity.type == "text_mention":
            if entity.user and me.id == entity.user.id:
                return True

    return False


@bot.message_handler(func=lambda message: message.chat.type == "private")
def handle_private(message):
    if not message.text:
        return

    if message.text.startswith("/"):
        return

    insult_text = message.text
    discord_id, tg_nick = random.choice(list(PARTICIPANTS.items()))

    bot.reply_to(message, f"Под раздачу попал @{tg_nick}")

    discord_message_id = send_to_discord(insult_text, discord_id)

    if discord_message_id:
        db.save_insult(
            discord_message_id=discord_message_id,
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            telegram_user_id=message.from_user.id,
            telegram_username=message.from_user.username or "no_username",
            victim_discord_id=discord_id,
            victim_tg_nick=tg_nick,
            insult_text=insult_text,
        )
        print(f"✅ Сохранено: Discord ID {discord_message_id} -> Telegram {message.chat.id}")
    else:
        bot.reply_to(message, "❌ Не удалось отправить сообщение в Discord. Проверь вебхук.")


@bot.message_handler(func=lambda message: message.chat.type in ["group", "supergroup"])
def handle_group(message):
    text = message.text or message.caption
    if not text:
        return

    if not is_bot_mentioned(message):
        return

    bot_username = f"@{bot.get_me().username}"
    insult_text = text.replace(bot_username, "").replace(bot_username.lower(), "").strip()
    if not insult_text:
        return

    discord_id, tg_nick = random.choice(list(PARTICIPANTS.items()))
    bot.reply_to(message, f"Под раздачу попал @{tg_nick}")

    discord_message_id = send_to_discord(insult_text, discord_id)
    if discord_message_id:
        db.save_insult(
            discord_message_id=discord_message_id,
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            telegram_user_id=message.from_user.id,
            telegram_username=message.from_user.username or "no_username",
            victim_discord_id=discord_id,
            victim_tg_nick=tg_nick,
            insult_text=insult_text,
        )


def run_telegram_bot():
    print("🤖 Telegram бот запущен...")
    bot.remove_webhook()
    bot.polling(none_stop=True)
