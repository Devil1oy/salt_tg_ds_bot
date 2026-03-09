# database.py - работа с базой данных
import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_file="insults.db"):
        # Исправлено: сохраняем имя файла для использования в других методах
        self.db_file = db_file
        self.conn = None
        self.create_tables()
    
    def create_tables(self):
        # Создаем новое соединение для создания таблиц
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS insults (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_message_id TEXT UNIQUE,
                telegram_chat_id TEXT,
                telegram_message_id TEXT,
                telegram_user_id TEXT,
                telegram_username TEXT,
                victim_discord_id TEXT,
                victim_tg_nick TEXT,
                insult_text TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weapon_aliases (
                weapon_name TEXT PRIMARY KEY,
                weapon_url TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        # Исправлено: открываем постоянное соединение после создания таблиц
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
    
    def save_insult(self, discord_message_id, telegram_chat_id, telegram_message_id, 
                   telegram_user_id, telegram_username, victim_discord_id, victim_tg_nick, insult_text):
        # Исправлено: проверяем, что соединение открыто
        if not self.conn:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO insults 
            (discord_message_id, telegram_chat_id, telegram_message_id, telegram_user_id, 
             telegram_username, victim_discord_id, victim_tg_nick, insult_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (str(discord_message_id), str(telegram_chat_id), str(telegram_message_id), 
              str(telegram_user_id), telegram_username, victim_discord_id, victim_tg_nick, insult_text))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_insult_by_discord_message(self, discord_message_id):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM insults WHERE discord_message_id = ?
        ''', (str(discord_message_id),))
        
        # Исправлено: правильное получение данных
        row = cursor.fetchone()
        if row:
            # Получаем названия колонок
            cursor2 = self.conn.cursor()
            cursor2.execute('PRAGMA table_info(insults)')
            columns = [col[1] for col in cursor2.fetchall()]
            return dict(zip(columns, row))
        return None
    
    def get_insult_by_tracking_data(self, telegram_chat_id, telegram_message_id):
        # Новый метод для поиска по данным Telegram
        if not self.conn:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM insults 
            WHERE telegram_chat_id = ? AND telegram_message_id = ?
        ''', (str(telegram_chat_id), str(telegram_message_id)))
        
        row = cursor.fetchone()
        if row:
            cursor2 = self.conn.cursor()
            cursor2.execute('PRAGMA table_info(insults)')
            columns = [col[1] for col in cursor2.fetchall()]
            return dict(zip(columns, row))
        return None
    
    def get_all_insults(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM insults ORDER BY timestamp DESC')
        
        # Исправлено: правильное получение всех записей
        rows = cursor.fetchall()
        cursor2 = self.conn.cursor()
        cursor2.execute('PRAGMA table_info(insults)')
        columns = [col[1] for col in cursor2.fetchall()]
        
        result = []
        for row in rows:
            result.append(dict(zip(columns, row)))
        return result

    def upsert_weapon_aliases(self, aliases):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)

        cursor = self.conn.cursor()
        cursor.executemany(
            '''
            INSERT INTO weapon_aliases (weapon_name, weapon_url, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(weapon_name) DO UPDATE SET
                weapon_url = excluded.weapon_url,
                updated_at = CURRENT_TIMESTAMP
            ''',
            aliases,
        )
        self.conn.commit()

    def get_weapon_url_by_name(self, weapon_name):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)

        cursor = self.conn.cursor()
        cursor.execute(
            '''
            SELECT weapon_url
            FROM weapon_aliases
            WHERE lower(weapon_name) = lower(?)
            ''',
            (weapon_name,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def get_all_weapon_aliases(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_file, check_same_thread=False)

        cursor = self.conn.cursor()
        cursor.execute(
            '''
            SELECT weapon_name, weapon_url
            FROM weapon_aliases
            '''
        )
        return cursor.fetchall()
