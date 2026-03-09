# discord_bot.py
import asyncio
import html

import discord
from discord import app_commands
import requests

from database import Database
from config import TELEGRAM_TOKEN, DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
from pubg_api import (
    build_gun_list_text_and_aliases,
    build_random_loadout,
    format_suggestions_text,
    format_weapon_details_text,
    get_weapon_details_by_url,
    resolve_weapon_url,
)


class DiscordResponseBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        super().__init__(intents=intents)
        self.db = Database()
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        @self.tree.command(name="gun", description="Список оружия PUBG или карточка по имени/url")
        @app_commands.describe(query="Имя или url оружия. Пусто = показать список")
        async def gun_slash(interaction: discord.Interaction, query: str | None = None):
            try:
                if not query:
                    guns_text, aliases = build_gun_list_text_and_aliases()
                    if aliases:
                        self.db.upsert_weapon_aliases(aliases)
                    await interaction.response.send_message(guns_text)
                    return

                if query.strip().lower() == "random":
                    summary, embeds = self._build_random_message_payload()
                    await interaction.response.send_message(content=summary, embeds=embeds)
                    return

                embed = await self._build_weapon_embed(query)
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                print(f"Ошибка /gun (Discord Slash): {e}")
                msg = "❌ Не удалось получить данные по оружию."
                if interaction.response.is_done():
                    await interaction.followup.send(msg)
                else:
                    await interaction.response.send_message(msg)

        await self.tree.sync()

    async def on_ready(self):
        print(f"Discord бот запущен как {self.user}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        # Обрабатываем только один заданный канал, если DISCORD_CHANNEL_ID указан.
        if DISCORD_CHANNEL_ID:
            try:
                if message.channel.id != int(DISCORD_CHANNEL_ID):
                    return
            except (TypeError, ValueError):
                pass

        content = (message.content or "").strip()
        if content.lower().startswith("/gun"):
            try:
                parts = content.split(maxsplit=1)

                if len(parts) == 1:
                    guns_text, aliases = build_gun_list_text_and_aliases()
                    if aliases:
                        self.db.upsert_weapon_aliases(aliases)
                    await message.reply(guns_text)
                    return

                query = parts[1]
                if query.strip().lower() == "random":
                    summary, embeds = self._build_random_message_payload()
                    await message.reply(content=summary, embeds=embeds)
                    return

                embed = await self._build_weapon_embed(query)
                await message.reply(embed=embed)
            except Exception as e:
                print(f"Ошибка /gun (Discord): {e}")
                await message.reply(f"❌ Не удалось получить данные по оружию. {e}")
            return

        if not (message.reference and message.reference.message_id):
            return

        try:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
            if replied_message.webhook_id is None:
                return

            insult_data = self.db.get_insult_by_discord_message(str(replied_message.id))
            if insult_data:
                await self.send_telegram_reply(
                    chat_id=insult_data["telegram_chat_id"],
                    reply_to_message_id=insult_data["telegram_message_id"],
                    response_text=message.content,
                    original_author=message.author.name,
                )
                await message.add_reaction("✅")
            else:
                print(f"Не найдено в БД: {replied_message.id}")

        except Exception as e:
            print(f"Ошибка при обработке ответа: {e}")


    async def send_telegram_reply(self, chat_id, reply_to_message_id, response_text, original_author):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

            safe_author = html.escape(str(original_author or "Неизвестно"))
            safe_response_text = html.escape(str(response_text or "(без текста)"))
            full_text = (
                f"<b>{safe_author}</b> ответил на твое сообщение в Discord:\n\n"
                f"{safe_response_text}"
            )

            data = {
                "chat_id": chat_id,
                "text": full_text,
                "reply_to_message_id": int(reply_to_message_id),
                "parse_mode": "HTML",
            }

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=data, timeout=10),
            )

            if response.status_code == 200:
                print(f"Ответ отправлен в Telegram (чат {chat_id})")
            else:
                print(f"Ошибка отправки в Telegram: {response.text}")

        except Exception as e:
            print(f"Ошибка при отправке в Telegram: {e}")

    async def _build_weapon_embed(self, query):
        weapon_url, suggestions = resolve_weapon_url(query, self.db)
        if not weapon_url:
            _, aliases = build_gun_list_text_and_aliases()
            if aliases:
                self.db.upsert_weapon_aliases(aliases)
            weapon_url, suggestions = resolve_weapon_url(query, self.db)

        if not weapon_url:
            raise ValueError("Оружие не найдено." + format_suggestions_text(suggestions))

        details = get_weapon_details_by_url(weapon_url)
        text = format_weapon_details_text(details)
        image_url = details.get("image")

        embed = discord.Embed(description=text)
        embed.title = details.get("name") or "Оружие"
        if image_url:
            embed.set_image(url=image_url)
        return embed

    def _build_random_message_payload(self):
        main_weapons, optional_pistol = build_random_loadout()
        summary = (
            "Случайный набор:\n"
            f"1) {main_weapons[0]['name']}\n"
            f"2) {main_weapons[1]['name']}\n"
            f"Опционально (пистолет): {optional_pistol['name']}"
        )

        embeds = []
        for idx, weapon in enumerate(main_weapons, start=1):
            embed = discord.Embed(title=f"{idx}) {weapon['name']}")
            embed.set_image(url=weapon["image"])
            embeds.append(embed)

        pistol_embed = discord.Embed(title=f"Опционально (пистолет): {optional_pistol['name']}")
        pistol_embed.set_image(url=optional_pistol["image"])
        embeds.append(pistol_embed)
        return summary, embeds


def run_discord_bot():
    client = DiscordResponseBot()
    client.run(DISCORD_BOT_TOKEN)
