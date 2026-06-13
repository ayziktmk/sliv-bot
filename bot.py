import asyncio
import logging
import os
import json
import re
import psycopg2
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

if not API_TOKEN:
    print("❌ BOT_TOKEN topilmadi!")
    exit(1)
if not DATABASE_URL:
    print("❌ DATABASE_URL topilmadi!")
    exit(1)

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

broadcast_logger = logging.getLogger("broadcast")
broadcast_logger.setLevel(logging.WARNING)
_fh = logging.FileHandler("broadcast_errors.log", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
broadcast_logger.addHandler(_fh)

# ==================== KANALLAR ====================
CHANNELS_FILE = "channels.json"

def load_channels():
    try:
        if os.path.exists(CHANNELS_FILE):
            with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return (data.get("channels", []), data.get("links", []),
                        data.get("private_channels", []), data.get("private_links", []))
    except Exception as e:
        print(f"❌ Kanal yuklashda xatolik: {e}")
    return [], [], [], []

def save_channels(channels, links, private_channels=None, private_links=None):
    try:
        data = {
            "channels": channels, "links": links,
            "private_channels": private_channels or [],
            "private_links": private_links or [],
            "updated": datetime.now().isoformat()
        }
        with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Kanal saqlashda xatolik: {e}")
        return False

CHANNELS, CHANNEL_LINKS, PRIVATE_CHANNELS, PRIVATE_LINKS = load_channels()

# ==================== BOT OBUNALARI ====================
BOT_SUBS_FILE = "bot_subscriptions.json"

def load_bot_subscriptions():
    try:
        if os.path.exists(BOT_SUBS_FILE):
            with open(BOT_SUBS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return []

def save_bot_subscriptions(data):
    try:
        with open(BOT_SUBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

BOT_SUBSCRIPTIONS = load_bot_subscriptions()

# ==================== ADD BUTTONS ====================
ADD_BUTTONS_FILE = "add_buttons.json"

def load_add_buttons():
    try:
        if os.path.exists(ADD_BUTTONS_FILE):
            with open(ADD_BUTTONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"_global": []}

def save_add_buttons(data):
    try:
        with open(ADD_BUTTONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

ADD_BUTTONS = load_add_buttons()

# ==================== JANRLAR ====================
GENRES_FILE = "genres.json"

def load_genres():
    try:
        if os.path.exists(GENRES_FILE):
            with open(GENRES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_genres(data):
    try:
        with open(GENRES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

MOVIE_GENRES = load_genres()

# ==================== MATNLAR ====================
TEXTS = {
    "uz": {
        "welcome": "🔞 <b>Sizga kerak bo'lgan videolar!</b>\n\n:",
        "welcome_back": "🔞 <b>Xush kelibsiz!</b>\n\n🔞kodni yuboring🔞:",
        "channels": "📋 <b>Kanallarga a'zo bo'ling:</b>\n\n<i>A'zo bo'lgandan so'ng kod qaytadan yuboring.</i>",
        "check_btn": "✅ Tekshirish",
        "success": "🎉 <b>Tabriklaymiz!</b>\n\nEndi botdan foydalanishingiz mumkin!\n\kodni qaytadan yuboring🔞:",
        "not_subscribed": "❌ Hali barcha kanallarga a'zo emassiz!",
        "not_subscribed_msg": "❌ <b>Avval kanallarga a'zo bo'ling!</b>",
        "movie_not_found": "❌ video topilmadi.",
        "loading": "⏳ Yuklanmoqda...",
        "error": "❌ Video yuborib bo'lmadi.",
        "search_prompt": "🔍 Kodni kiriting:",
        "lang_changed": "✅ Til o'zgartirildi!",
    },
   
}

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

async def set_bot_description():
    try:
        await bot.set_my_description("Kino kodlari orqali kino yuklab beradi")
        await bot.set_my_short_description("Instagram blogerlari🔞 , maktab qizlarini yigiti bilan qigan ishlari🔞 , ozbekcha videolar🔞 ")
    except:
        pass

# ==================== POSTGRESQL ====================
def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS movies (
        code TEXT PRIMARY KEY, file_id TEXT NOT NULL, name TEXT NOT NULL,
        views INTEGER DEFAULT 0, downloads INTEGER DEFAULT 0, last_viewed TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS movie_parts (
        id SERIAL PRIMARY KEY, code TEXT NOT NULL, part_number INTEGER NOT NULL,
        file_id TEXT NOT NULL, part_name TEXT NOT NULL, views INTEGER DEFAULT 0,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, added_by BIGINT,
        UNIQUE(code, part_number))""")
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
        subscribed BOOLEAN DEFAULT FALSE,
        joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_blocked_bot BOOLEAN DEFAULT FALSE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS advertisements (
        id SERIAL PRIMARY KEY, message_id BIGINT, user_id BIGINT, chat_id BIGINT,
        message_type TEXT, sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_deleted BOOLEAN DEFAULT FALSE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS movie_stats (
        id SERIAL PRIMARY KEY, movie_code TEXT, user_id BIGINT, action TEXT,
        action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_languages (
        user_id BIGINT PRIMARY KEY, language TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS channel_subscribers (
        id SERIAL PRIMARY KEY, channel_username TEXT NOT NULL, user_id BIGINT NOT NULL,
        joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(channel_username, user_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS join_requests (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        channel_key TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'requested',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, channel_key))""")
    c.execute("""CREATE TABLE IF NOT EXISTS contact_messages (
        id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, username TEXT,
        first_name TEXT, message_text TEXT, message_type TEXT DEFAULT 'text',
        is_answered BOOLEAN DEFAULT FALSE,
        sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS film_orders (
        id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, username TEXT,
        first_name TEXT, order_text TEXT NOT NULL, is_done BOOLEAN DEFAULT FALSE,
        ordered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS favorites (
        id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, movie_code TEXT NOT NULL,
        movie_name TEXT NOT NULL, added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, movie_code))""")
    c.execute("""CREATE TABLE IF NOT EXISTS bot_sub_users (
        id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL, bot_username TEXT NOT NULL,
        started_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, bot_username))""")
    conn.commit()
    conn.close()
    print("✅ PostgreSQL DB initialized")

# ==================== USER DB ====================
def add_user_to_db(user_id, username, first_name, last_name, subscribed=False):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""INSERT INTO users (user_id, username, first_name, last_name, subscribed)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET username=%s, first_name=%s, last_name=%s, last_active=CURRENT_TIMESTAMP,
            is_blocked_bot=FALSE""",
            (user_id, username, first_name, last_name, subscribed, username, first_name, last_name))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ add_user: {e}")

def save_user_language(user_id, language):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO user_languages (user_id, language) VALUES (%s,%s) ON CONFLICT (user_id) DO UPDATE SET language=%s",
                  (user_id, language, language))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ save_lang: {e}")

def get_user_language(user_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT language FROM user_languages WHERE user_id=%s", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None

def get_all_users():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except:
        return []

def get_active_users():
    try:
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked_bot BOOLEAN DEFAULT FALSE")
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        c.execute("SELECT user_id FROM users WHERE is_blocked_bot IS NOT TRUE")
        rows = c.fetchall()
        conn.close()
        result = [r[0] for r in rows]
        print(f"[DB] get_active_users: {len(result)} ta faol user")
        return result
    except Exception as e:
        print(f"[DB] get_active_users xato: {e}")
        try:
            conn2 = get_db()
            c2 = conn2.cursor()
            c2.execute("SELECT user_id FROM users")
            rows2 = c2.fetchall()
            conn2.close()
            return [r[0] for r in rows2]
        except Exception as e2:
            print(f"[DB] get_active_users fallback xato: {e2}")
            return []

def mark_user_blocked_bot(user_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_blocked_bot=TRUE WHERE user_id=%s", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

# ==================== BOT OBUNA DB ====================
def log_bot_sub_user(user_id, bot_username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO bot_sub_users (user_id, bot_username) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                  (user_id, bot_username))
        conn.commit()
        conn.close()
    except:
        pass

def check_bot_sub_in_db(user_id, bot_username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM bot_sub_users WHERE user_id=%s AND bot_username=%s",
                  (user_id, bot_username))
        result = c.fetchone()
        conn.close()
        return result is not None
    except:
        return False

def get_bot_sub_stats(bot_username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM bot_sub_users WHERE bot_username=%s", (bot_username,))
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM bot_sub_users WHERE bot_username=%s AND started_date >= NOW() - INTERVAL '1 day'", (bot_username,))
        today = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM bot_sub_users WHERE bot_username=%s AND started_date >= NOW() - INTERVAL '7 days'", (bot_username,))
        week = c.fetchone()[0]
        conn.close()
        return {"total": total, "today": today, "week": week}
    except:
        return {"total": 0, "today": 0, "week": 0}

# ==================== KINO DB ====================
def add_movie_to_db(code, file_id, name):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO movies (code, file_id, name) VALUES (%s,%s,%s)", (code, file_id, name))
        conn.commit()
        conn.close()
        return True
    except psycopg2.IntegrityError:
        return False
    except Exception as e:
        print(f"❌ add_movie: {e}")
        return False

def get_movie_from_db(code):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT file_id, name FROM movies WHERE code=%s", (code,))
        result = c.fetchone()
        conn.close()
        return result
    except:
        return None

def delete_movie_from_db(code):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM movies WHERE code=%s", (code,))
        rows = c.rowcount
        c.execute("DELETE FROM movie_parts WHERE code=%s", (code,))
        conn.commit()
        conn.close()
        return rows > 0
    except Exception as e:
        print(f"❌ delete_movie: {e}")
        return False

def get_all_movies():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT code, name FROM movies ORDER BY code")
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

def clear_all_movies():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM movies")
        rows = c.rowcount
        c.execute("DELETE FROM movie_parts")
        conn.commit()
        conn.close()
        return rows
    except:
        return 0

def increment_movie_view(movie_code, user_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE movies SET views=views+1, last_viewed=CURRENT_TIMESTAMP WHERE code=%s", (movie_code,))
        c.execute("INSERT INTO movie_stats (movie_code, user_id, action) VALUES (%s,%s,'view')", (movie_code, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ increment_view: {e}")

def get_top_movies_for_users(limit=5):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT m.code, m.name, COUNT(ms.id) as view_count
            FROM movies m LEFT JOIN movie_stats ms ON m.code=ms.movie_code AND ms.action='view'
            GROUP BY m.code, m.name ORDER BY view_count DESC LIMIT %s""", (limit,))
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

# ==================== KO'P QISMLI ====================
def add_movie_part(code, part_number, file_id, part_name, added_by):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""INSERT INTO movie_parts (code, part_number, file_id, part_name, added_by)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT (code, part_number) DO UPDATE SET file_id=%s, part_name=%s""",
            (code, part_number, file_id, part_name, added_by, file_id, part_name))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ add_movie_part: {e}")
        return False

def get_movie_parts(code):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT part_number, file_id, part_name, views FROM movie_parts WHERE code=%s ORDER BY part_number", (code,))
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

def get_movie_part(code, part_number):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT file_id, part_name FROM movie_parts WHERE code=%s AND part_number=%s", (code, part_number))
        result = c.fetchone()
        conn.close()
        return result
    except:
        return None

def increment_part_view(code, part_number, user_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE movie_parts SET views=views+1 WHERE code=%s AND part_number=%s", (code, part_number))
        c.execute("INSERT INTO movie_stats (movie_code, user_id, action) VALUES (%s,%s,'view')",
                  (f"{code}_p{part_number}", user_id))
        conn.commit()
        conn.close()
    except:
        pass

def get_all_parts_list():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT code, COUNT(*) as parts_count,
                   STRING_AGG(part_name, ', ' ORDER BY part_number) as parts
                   FROM movie_parts GROUP BY code ORDER BY code""")
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

# ==================== SEVIMLILAR ====================
def add_to_favorites(user_id, movie_code, movie_name):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO favorites (user_id, movie_code, movie_name) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id",
                  (user_id, movie_code, movie_name))
        result = c.fetchone()
        conn.commit()
        conn.close()
        return result is not None
    except:
        return False

def remove_from_favorites(user_id, movie_code):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM favorites WHERE user_id=%s AND movie_code=%s", (user_id, movie_code))
        rows = c.rowcount
        conn.commit()
        conn.close()
        return rows > 0
    except:
        return False

def get_user_favorites(user_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT movie_code, movie_name, added_date FROM favorites WHERE user_id=%s ORDER BY added_date DESC", (user_id,))
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

def is_in_favorites(user_id, movie_code):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM favorites WHERE user_id=%s AND movie_code=%s", (user_id, movie_code))
        result = c.fetchone()
        conn.close()
        return result is not None
    except:
        return False

# ==================== STATISTIKA ====================
def get_top_movies_by_time(time_period='day'):
    try:
        conn = get_db()
        c = conn.cursor()
        intervals = {'day': "1 day", 'week': "7 days", 'month': "30 days",
                     '6month': "180 days", 'year': "365 days", 'all': "36500 days"}
        interval = intervals.get(time_period, "1 day")
        c.execute(f"""SELECT m.code, m.name, COUNT(ms.id) as view_count
            FROM movies m LEFT JOIN movie_stats ms ON m.code=ms.movie_code
                AND ms.action='view' AND ms.action_date >= NOW() - INTERVAL '{interval}'
            GROUP BY m.code, m.name ORDER BY view_count DESC LIMIT 20""")
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

def get_total_stats():
    result = {
        'today_views': 0, 'week_views': 0, 'month_views': 0, 'total_views': 0,
        'total_users': 0, 'blocked_users': 0, 'today_new': 0, 'week_new': 0,
        'active_today': 0, 'subscribed': 0, 'top_movie': None,
        'movie_count': 0, 'series_count': 0, 'pending_orders': 0, 'unanswered': 0
    }
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM movie_stats WHERE action='view' AND DATE(action_date)=CURRENT_DATE")
        result['today_views'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM movie_stats WHERE action='view' AND action_date >= NOW() - INTERVAL '7 days'")
        result['week_views'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM movie_stats WHERE action='view' AND action_date >= NOW() - INTERVAL '30 days'")
        result['month_views'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM movie_stats WHERE action='view'")
        result['total_views'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users")
        result['total_users'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE is_blocked_bot IS TRUE")
        result['blocked_users'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE DATE(joined_date)=CURRENT_DATE")
        result['today_new'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE joined_date >= NOW() - INTERVAL '7 days'")
        result['week_new'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE last_active >= NOW() - INTERVAL '1 day'")
        result['active_today'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE subscribed=TRUE")
        result['subscribed'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM movies")
        result['movie_count'] = c.fetchone()[0]

        c.execute("SELECT COUNT(DISTINCT code) FROM movie_parts")
        result['series_count'] = c.fetchone()[0]

        c.execute("""SELECT m.code, m.name, COUNT(ms.id) as vc
            FROM movies m
            LEFT JOIN movie_stats ms ON m.code=ms.movie_code AND ms.action='view'
            GROUP BY m.code, m.name
            ORDER BY vc DESC LIMIT 1""")
        result['top_movie'] = c.fetchone()

        c.execute("SELECT COUNT(*) FROM film_orders WHERE is_done=FALSE")
        result['pending_orders'] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM contact_messages WHERE is_answered=FALSE")
        result['unanswered'] = c.fetchone()[0]

    except Exception as e:
        print(f"❌ get_total_stats: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass
    return result

# ==================== REKLAMA DB ====================
def add_advertisement_to_db(message_id, user_id, chat_id, message_type):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO advertisements (message_id, user_id, chat_id, message_type) VALUES (%s,%s,%s,%s) RETURNING id",
            (message_id, user_id, chat_id, message_type)
        )
        ad_id = c.fetchone()[0]
        conn.commit()
        conn.close()
        return ad_id
    except Exception as e:
        broadcast_logger.error(f"add_advertisement_to_db: {e}")
        return None

def get_all_sent_advertisements():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT a.id, a.message_id, a.user_id, u.username, u.first_name,
                   a.message_type, a.sent_date, a.is_deleted, a.chat_id
                   FROM advertisements a LEFT JOIN users u ON a.user_id=u.user_id
                   ORDER BY a.sent_date DESC""")
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

def log_channel_subscriber(channel_username, user_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO channel_subscribers (channel_username, user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                  (channel_username, user_id))
        conn.commit()
        conn.close()
    except:
        pass

def save_join_request(user_id: int, channel_key: str):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO join_requests (user_id, channel_key, status, updated_at)
            VALUES (%s, %s, 'requested', NOW())
            ON CONFLICT (user_id, channel_key)
            DO UPDATE SET status='requested', updated_at=NOW()
        """, (user_id, channel_key))
        conn.commit()
        conn.close()
        print(f"[JOIN_REQUEST] user={user_id} channel={channel_key} → requested")
    except Exception as e:
        print(f"❌ save_join_request: {e}")

def get_join_request_status(user_id: int, channel_key: str):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT status FROM join_requests WHERE user_id=%s AND channel_key=%s",
            (user_id, channel_key)
        )
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"❌ get_join_request_status: {e}")
        return None

def user_has_join_request(user_id, channel_key):
    status = get_join_request_status(user_id, channel_key)
    return status in ('requested', 'member')

def get_channel_subscriber_stats(channel_username, period='all'):
    try:
        conn = get_db()
        c = conn.cursor()
        intervals = {'today': "INTERVAL '1 day'", 'week': "INTERVAL '7 days'",
                     'month': "INTERVAL '30 days'", 'year': "INTERVAL '365 days'",
                     'all': "INTERVAL '36500 days'"}
        interval = intervals.get(period, "INTERVAL '36500 days'")
        c.execute(f"SELECT COUNT(*) FROM channel_subscribers WHERE channel_username=%s AND joined_date >= NOW() - {interval}",
                  (channel_username,))
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

def save_contact_message(user_id, username, first_name, message_text, message_type='text'):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO contact_messages (user_id, username, first_name, message_text, message_type) VALUES (%s,%s,%s,%s,%s)",
                  (user_id, username, first_name, message_text, message_type))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def save_film_order(user_id, username, first_name, order_text):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO film_orders (user_id, username, first_name, order_text) VALUES (%s,%s,%s,%s) RETURNING id",
                  (user_id, username, first_name, order_text))
        order_id = c.fetchone()[0]
        conn.commit()
        conn.close()
        return order_id
    except:
        return None

def get_pending_orders():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, username, first_name, order_text, ordered_date FROM film_orders WHERE is_done=FALSE ORDER BY ordered_date DESC")
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

def mark_order_done(order_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE film_orders SET is_done=TRUE WHERE id=%s", (order_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

# ==================== OBUNA TEKSHIRUVI ====================
async def check_single_channel(user_id, channel):
    try:
        ch = channel if channel.startswith('@') else '@' + channel
        member = await bot.get_chat_member(ch, user_id)
        status = str(member.status)
        if status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
    except Exception as e:
        err = str(e).lower()
        if 'chat not found' in err:
            print(f"⚠️ Kanal topilmadi: {channel}")
            return True
        elif 'bot is not a member' in err or 'not enough rights' in err:
            print(f"⚠️ Bot kanalda admin emas: {channel}")
            return True
        elif 'user not found' in err or 'participant' in err:
            return False
        elif 'forbidden' in err:
            print(f"⚠️ Kanalga kirish forbidden: {channel}")
            return False
        else:
            print(f"⚠️ Kutilmagan xato {channel}: {err[:100]}")
            return False

async def check_bot_subscription(user_id, bot_sub):
    bot_username = bot_sub.get("username", "")
    if not bot_username:
        return True
    return check_bot_sub_in_db(user_id, bot_username)

async def get_not_subscribed_channels(user_id):
    not_subscribed = []

    # 1. Ochiq kanallar
    if CHANNELS:
        tasks = [check_single_channel(user_id, ch) for ch in CHANNELS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for channel, result in zip(CHANNELS, results):
            if isinstance(result, Exception) or not result:
                not_subscribed.append({"type": "channel", "id": channel})

    # 2. Yopiq kanallar
    for channel in PRIVATE_CHANNELS:
        if not user_has_join_request(user_id, channel):
            not_subscribed.append({"type": "channel", "id": channel})

    # 3. Bot obunalari
    for bot_sub in BOT_SUBSCRIPTIONS:
        if not await check_bot_subscription(user_id, bot_sub):
            not_subscribed.append({
                "type": "bot",
                "id": bot_sub.get("username"),
                "link": bot_sub.get("link")
            })

    return not_subscribed

async def is_subscribed(user_id):
    try:
        return len(await get_not_subscribed_channels(user_id)) == 0
    except:
        return False

def get_subscribe_keyboard_v2(lang="uz", not_subscribed=None):
    if not_subscribed is None:
        not_subscribed = []
    buttons = []
    channel_idx = 1
    bot_idx = 1
    for item in not_subscribed:
        if item["type"] == "channel":
            channel = item["id"]
            link = None
            if channel in CHANNELS:
                try:
                    idx = CHANNELS.index(channel)
                    link = CHANNEL_LINKS[idx] if idx < len(CHANNEL_LINKS) else None
                except:
                    link = None
            elif channel in PRIVATE_CHANNELS:
                try:
                    idx = PRIVATE_CHANNELS.index(channel)
                    link = PRIVATE_LINKS[idx] if idx < len(PRIVATE_LINKS) else None
                except:
                    link = None
            if link:
                btn_text = f"🔒 {channel_idx}-yopiq kanal" if channel in PRIVATE_CHANNELS else f"📢 {channel_idx}-kanal"
                buttons.append([InlineKeyboardButton(text=btn_text, url=link)])
            else:
                btn_text = f"🔒 {channel_idx}-yopiq kanal" if channel in PRIVATE_CHANNELS else f"📢 {channel_idx}-kanal"
                buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"no_link_{channel_idx}")])
            channel_idx += 1
        elif item["type"] == "bot":
            link = item.get("link", "")
            if link:
                buttons.append([InlineKeyboardButton(text=f"🤖 {bot_idx}-bot", url=link)])
                bot_idx += 1
    buttons.append([InlineKeyboardButton(text=TEXTS[lang]['check_btn'], callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==================== KEYBOARDLAR ====================
def get_user_main_keyboard():
    return ReplyKeyboardRemove()

def get_user_inline_menu(lang="uz"):
    labels = {
        "uz": {"fav": "⭐ Sevimlilar", "contact": "📞 Aloqa", "lang": "🌐 Til tanlash"},
        "ru": {"fav": "⭐ Избранное", "contact": "📞 Связь", "lang": "🌐 Язык"},
        "en": {"fav": "⭐ Favorites", "contact": "📞 Contact", "lang": "🌐 Language"},
    }
    lb = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lb["fav"], callback_data="menu_fav"),
         InlineKeyboardButton(text=lb["contact"], callback_data="menu_contact")],
        [InlineKeyboardButton(text=lb["lang"], callback_data="menu_lang")],
    ])

def get_admin_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎬 Kino qo'shish"), KeyboardButton(text="📋 Kinolar ro'yxati")],
        [KeyboardButton(text="🗑️ Kino o'chirish"), KeyboardButton(text="⚠️ Hammasini o'chir")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="👥 Foydalanuvchilar")],
        [KeyboardButton(text="📢 Reklama yuborish"), KeyboardButton(text="📡 Kanallar ro'yxati")],
        [KeyboardButton(text="🔧 Qo'shimcha buyruqlar")]
    ], resize_keyboard=True)

def get_admin_extra_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Reklamalar ro'yxati"), KeyboardButton(text="❌ Reklamani o'chirish")],
        [KeyboardButton(text="🔍 Obuna test"), KeyboardButton(text="⭐ Top kinolar")],
        [KeyboardButton(text="📈 Kanal statistikasi"), KeyboardButton(text="➕ Kanal qo'shish")],
        [KeyboardButton(text="➖ Kanal o'chirish"), KeyboardButton(text="🔒 Yopiq kanal qo'shish")],
        [KeyboardButton(text="🤖 Bot obunalari"), KeyboardButton(text="🔗 Add buttons boshqaruv")],
        [KeyboardButton(text="📬 Buyurtmalar"), KeyboardButton(text="💬 Xabarlar")],
        [KeyboardButton(text="🚫 User bloklash"), KeyboardButton(text="✅ Blokdan chiqarish")],
        [KeyboardButton(text="🏠 Asosiy panel")]
    ], resize_keyboard=True)

def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")]
    ])

def get_parts_keyboard(code, parts, lang="uz"):
    number_emojis = ["1️⃣","2️⃣","3️⃣","4️⃣",
                     "5️⃣","6️⃣","7️⃣","8️⃣",
                     "9️⃣","🔟"]
    buttons = []
    row = []
    for part_number, file_id, part_name, views in parts:
        if part_number <= 10:
            label = number_emojis[part_number - 1]
        else:
            label = f"{part_number}"
        row.append(InlineKeyboardButton(
            text=label,
            callback_data=f"part_{code}_{part_number}"
        ))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_top_movies_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕐 1 Kunlik", callback_data="top_day"),
         InlineKeyboardButton(text="📅 1 Haftalik", callback_data="top_week")],
        [InlineKeyboardButton(text="📊 1 Oylik", callback_data="top_month"),
         InlineKeyboardButton(text="⏳ 6 Oylik", callback_data="top_6month")],
        [InlineKeyboardButton(text="📈 1 Yillik", callback_data="top_year"),
         InlineKeyboardButton(text="🏆 Barchasi", callback_data="top_all")],
        [InlineKeyboardButton(text="📋 Umumiy statistika", callback_data="top_stats")]
    ])

def get_channel_stats_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Bugun", callback_data="chstat_today"),
         InlineKeyboardButton(text="📊 Hafta", callback_data="chstat_week")],
        [InlineKeyboardButton(text="📈 Oy", callback_data="chstat_month"),
         InlineKeyboardButton(text="🗓 Yil", callback_data="chstat_year")],
        [InlineKeyboardButton(text="🏆 Hammasi", callback_data="chstat_all")]
    ])

def get_contact_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Adminga xabar yozish", callback_data="contact_write")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="contact_back")]
    ])

def get_genre_keyboard(movie_code):
    genres = [
        "🎬 Drama", "😂 Komediya", "🔫 Jangovar", "😱 Triller",
        "🧬 Fantastika", "💑 Melodrama", "🧙 Fanteziya", "🔍 Detektiv",
        "👻 Dahshat", "🌍 Sarguzasht", "📺 Multfilm", "🎵 Musiqa"
    ]
    buttons = []
    row = []
    for genre in genres:
        row.append(InlineKeyboardButton(text=genre, callback_data=f"genre|{movie_code}|{genre}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"genre_skip|{movie_code}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_add_btn_keyboard(movie_code):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tugma qo'shish", callback_data=f"addbtn_yes_{movie_code}")],
        [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"addbtn_no_{movie_code}")]
    ])

def get_bot_sub_manage_keyboard():
    keyboard = []
    for i, bs in enumerate(BOT_SUBSCRIPTIONS):
        uname = bs.get("username", "")
        keyboard.append([
            InlineKeyboardButton(text=f"🤖 {uname}", callback_data=f"botsub_info_{i}"),
            InlineKeyboardButton(text="🗑", callback_data=f"botsub_del_{i}")
        ])
    keyboard.append([InlineKeyboardButton(text="➕ Bot qo'shish", callback_data="botsub_add")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_add_buttons_list_keyboard():
    keyboard = []
    global_btns = ADD_BUTTONS.get("_global", [])
    for i, btn in enumerate(global_btns):
        keyboard.append([
            InlineKeyboardButton(text=f"✏️ {btn['text']}", callback_data=f"editbtn|_global|{i}"),
            InlineKeyboardButton(text="🗑", callback_data=f"delbtn|_global|{i}")
        ])
    for target, btns in ADD_BUTTONS.items():
        if target == "_global":
            continue
        for i, btn in enumerate(btns):
            keyboard.append([
                InlineKeyboardButton(text=f"✏️ [{target}] {btn['text']}", callback_data=f"editbtn|{target}|{i}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delbtn|{target}|{i}")
            ])
    keyboard.append([
        InlineKeyboardButton(text="➕ Global tugma", callback_data="addbtn_global_new"),
        InlineKeyboardButton(text="➕ Kino tugmasi", callback_data="addbtn_movie_new")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==================== STATES ====================
class AdminStates(StatesGroup):
    waiting_for_movie_file = State()
    waiting_for_movie_code = State()
    waiting_for_movie_name = State()
    waiting_for_delete_code = State()
    waiting_for_advertisement = State()
    waiting_ad_buttons = State()
    waiting_for_delete_ad = State()
    waiting_for_channel_username = State()
    waiting_for_channel_link = State()
    waiting_for_delete_channel = State()
    waiting_part_code = State()
    waiting_part_video = State()
    waiting_part_name = State()
    waiting_part_number = State()
    waiting_private_channel = State()
    waiting_private_link = State()
    admin_reply_writing = State()
    add_btn_code = State()
    add_btn_text = State()
    add_btn_url = State()
    inline_add_btn_text = State()
    inline_add_btn_url = State()
    waiting_bot_username = State()
    waiting_bot_link = State()
    edit_btn_text = State()
    edit_btn_url = State()
    new_btn_movie_code = State()
    new_btn_text = State()
    new_btn_url = State()

class UserStates(StatesGroup):
    writing_contact = State()
    writing_search = State()
    writing_order = State()

# ==================== KINO YUBORISH ====================
async def send_movie_to_user(chat_id, file_id, movie_name, movie_code, user_id, lang="uz"):
    try:
        increment_movie_view(movie_code, user_id)
        kb = build_movie_keyboard(movie_code, movie_name, user_id)
        await bot.send_video(
            chat_id=chat_id,
            video=file_id,
            caption=f"🎬 {movie_name}\n🔢 Kodi: <code>{movie_code}</code>\n\n📥 Yuklab oling!",
            protect_content=True,
            reply_markup=kb
        )
        return True
    except Exception as e:
        print(f"❌ send_movie: {e}")
        return False

async def send_part_to_user(chat_id, file_id, part_name, movie_code, part_number, user_id):
    try:
        kb = build_movie_keyboard(movie_code, part_name, user_id)
        await bot.send_video(
            chat_id=chat_id,
            video=file_id,
            caption=f"🎬 {part_name}\n🔢 Kodi: <code>{movie_code}</code> | {part_number}-qism\n\n📥 Yuklab oling!",
            protect_content=True,
            reply_markup=kb
        )
        return True
    except Exception as e:
        print(f"❌ send_part: {e}")
        return False

def build_movie_keyboard(movie_code, movie_name, user_id, show_fav=True):
    extra_btns = get_movie_extra_buttons(movie_code)
    rows = []
    for i in range(0, len(extra_btns), 2):
        rows.append(extra_btns[i:i+2])
    if show_fav:
        in_fav = is_in_favorites(user_id, movie_code)
        fav_text = "❤️ Sevimlilardan chiqar" if in_fav else "🤍 Sevimlilarga qo'sh"
        rows.append([InlineKeyboardButton(text=fav_text, callback_data=f"fav_{movie_code}")])
    if rows:
        return InlineKeyboardMarkup(inline_keyboard=rows)
    return None

def get_movie_extra_buttons(movie_code):
    buttons = []
    for btn in ADD_BUTTONS.get("_global", []):
        text = btn.get("text", "")
        url = btn.get("url", "")
        if text and url:
            buttons.append(InlineKeyboardButton(text=text, url=url))
    for btn in ADD_BUTTONS.get(movie_code, []):
        text = btn.get("text", "")
        url = btn.get("url", "")
        if text and url:
            buttons.append(InlineKeyboardButton(text=text, url=url))
    return buttons

# ==================== START (TUZATILGAN - update_user_subscription YO'Q) ====================
@dp.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = message.from_user
    start_payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    if start_payload.startswith("botsub_"):
        source_bot = start_payload.replace("botsub_", "")
        for bs in BOT_SUBSCRIPTIONS:
            uname = bs.get("username", "").lstrip("@")
            if uname.lower() == source_bot.lower():
                log_bot_sub_user(user_id, bs.get("username"))
                break
    add_user_to_db(user_id, user.username, user.first_name, user.last_name, False)
    lang = get_user_language(user_id)
    if lang is None:
        await message.answer(TEXTS["uz"]["welcome"], reply_markup=get_language_keyboard())
        return
    # REAL VAQTDA TEKSHIRUV - subscribed bazaga saqlanmaydi
    await message.answer(
        TEXTS[lang]['welcome_back'],
        reply_markup=get_user_inline_menu(lang)
    )

# ==================== LANGUAGE CALLBACK ====================
@dp.callback_query(F.data.startswith("lang_"))
async def language_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    lang = callback_query.data.split("_")[1]
    save_user_language(user_id, lang)
    try:
        await callback_query.message.delete()
    except:
        pass
    not_sub = await get_not_subscribed_channels(user_id)
    if not_sub:
        await callback_query.message.answer(TEXTS[lang]['channels'], reply_markup=get_subscribe_keyboard_v2(lang, not_sub))
    else:
        await callback_query.message.answer(TEXTS[lang]['success'], reply_markup=get_user_inline_menu(lang))
    await callback_query.answer()

# ==================== CHECK SUBSCRIPTION (TUZATILGAN - update_user_subscription YO'Q) ====================
@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    lang = get_user_language(user_id) or "uz"
    not_sub = await get_not_subscribed_channels(user_id)
    if not not_sub:
        # REAL VAQTDA TEKSHIRUV - subscribed bazaga saqlanmaydi
        for channel in CHANNELS:
            ch = channel if channel.startswith('@') else '@' + channel
            log_channel_subscriber(ch, user_id)
        try:
            await callback_query.message.delete()
        except:
            pass
        await callback_query.message.answer(
            TEXTS[lang]['success'],
            reply_markup=get_user_inline_menu(lang)
        )
    else:
        try:
            await callback_query.message.edit_text(TEXTS[lang]['channels'], reply_markup=get_subscribe_keyboard_v2(lang, not_sub))
        except:
            pass
        await callback_query.answer(TEXTS[lang]['not_subscribed'], show_alert=True)
        return
    await callback_query.answer()

# ==================== QOLGAN FUNKSIYALAR (TO'LIQ) ====================
@dp.callback_query(F.data == "contact_back")
async def contact_back(callback_query: types.CallbackQuery):
    try:
        await callback_query.message.delete()
    except:
        pass
    await callback_query.answer()

# ==================== YOPIQ KANAL JOIN REQUEST ====================
@dp.chat_join_request()
async def handle_join_request(update: types.ChatJoinRequest):
    user_id = update.from_user.id
    chat_id = update.chat.id
    chat_id_str = str(chat_id)
    username = (update.chat.username or "").lower().lstrip("@")
    channel_title = update.chat.title or ""

    print(f"[JOIN_REQUEST] user={user_id}, chat_id={chat_id_str}, username='{username}', title='{channel_title}'")
    print(f"[JOIN_REQUEST] PRIVATE_CHANNELS = {PRIVATE_CHANNELS}")

    matched_key = None

    for saved_ch in PRIVATE_CHANNELS:
        saved_clean = saved_ch.strip()
        
        if saved_clean == chat_id_str:
            matched_key = saved_ch
            print(f"[JOIN_REQUEST] Matched by chat_id: {matched_key}")
            break
        
        if username and saved_clean.lstrip("@").lower() == username:
            matched_key = saved_ch
            print(f"[JOIN_REQUEST] Matched by username: {matched_key}")
            break
        
        def extract_digits(s):
            cleaned = s.lstrip("-@")
            if cleaned.startswith("100") and len(cleaned) > 3:
                cleaned = cleaned[3:]
            return cleaned
        
        if extract_digits(saved_clean) == extract_digits(chat_id_str):
            matched_key = saved_ch
            print(f"[JOIN_REQUEST] Matched by digits: {matched_key}")
            break

    if matched_key:
        save_join_request(user_id, matched_key)
        log_channel_subscriber(matched_key, user_id)
        print(f"[JOIN_REQUEST] ✅ user={user_id} → {matched_key} saqlandi")
    else:
        if PRIVATE_CHANNELS:
            for ch in PRIVATE_CHANNELS:
                save_join_request(user_id, ch)
                log_channel_subscriber(ch, user_id)
            print(f"[JOIN_REQUEST] ⚠️ user={user_id} chat={chat_id_str} mos topilmadi, barcha yopiq kanallarga yozildi")
        else:
            print(f"[JOIN_REQUEST] ⚠️ user={user_id} PRIVATE_CHANNELS bo'sh, hech narsa saqlanmadi")

# ==================== INLINE MENYU HANDLERLARI ====================
@dp.callback_query(F.data == "menu_fav")
async def menu_fav_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    lang = get_user_language(user_id) or "uz"
    favs = get_user_favorites(user_id)
    if not favs:
        await callback_query.answer("⭐ Sevimlilar bo'sh.", show_alert=True)
        return
    text = f"⭐ <b>Sevimlilarim ({len(favs)} ta):</b>\n\n"
    buttons = []
    for i, (code, name, added_date) in enumerate(favs, 1):
        text += f"{i}. 🎬 {name} (<code>{code}</code>)\n"
        buttons.append([
            InlineKeyboardButton(text=f"▶️ {name}", callback_data=f"search_{code}"),
            InlineKeyboardButton(text="🗑", callback_data=f"unfav_{code}")
        ])
    await callback_query.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback_query.answer()





# ==================== SEVIMLILAR ====================
@dp.callback_query(F.data.startswith("fav_"))
async def fav_toggle_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    movie_code = callback_query.data.replace("fav_", "")
    result = get_movie_from_db(movie_code)
    movie_name = result[1] if result else movie_code
    in_fav = is_in_favorites(user_id, movie_code)
    if in_fav:
        remove_from_favorites(user_id, movie_code)
        await callback_query.answer("💔 Sevimlilardan olib tashlandi.", show_alert=False)
        new_text = "🤍 Sevimlilarga qo'sh"
    else:
        add_to_favorites(user_id, movie_code, movie_name)
        await callback_query.answer("❤️ Sevimlilarga qo'shildi!", show_alert=False)
        new_text = "❤️ Sevimlilardan chiqar"
    try:
        old_kb = callback_query.message.reply_markup
        if old_kb:
            new_rows = []
            for row in old_kb.inline_keyboard:
                new_row = []
                for btn in row:
                    if btn.callback_data and btn.callback_data.startswith("fav_"):
                        new_row.append(InlineKeyboardButton(text=new_text, callback_data=btn.callback_data))
                    else:
                        new_row.append(btn)
                new_rows.append(new_row)
            await callback_query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_rows))
    except:
        pass

# ==================== QIDIRISH ====================
@dp.message(F.text == "🔍 Qidirish")
async def btn_search(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current is not None:
        return
    user_id = message.from_user.id
    lang = get_user_language(user_id) or "uz"
    if not await is_subscribed(user_id):
        not_sub = await get_not_subscribed_channels(user_id)
        await message.answer(TEXTS[lang]['not_subscribed_msg'], reply_markup=get_subscribe_keyboard_v2(lang, not_sub))
        return
    await state.set_state(UserStates.writing_search)
    await message.answer(
        "🔍 <b>Kino qidirish</b>\n\nKino kodini kiriting:\n\n<i>Bekor qilish uchun «❌ Bekor» tugmasini bosing</i>",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]],
                                         resize_keyboard=True, one_time_keyboard=False)
    )

@dp.message(UserStates.writing_search, F.text == "❌ Bekor")
async def process_search_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())

@dp.message(UserStates.writing_search)
async def process_search(message: types.Message, state: FSMContext):
    if not message.text:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return
    if message.text.strip() in ["❌ Bekor", "❌ bekor", "Bekor", "bekor", "❌"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return
    lang = get_user_language(message.from_user.id) or "uz"
    query = message.text.strip().upper()
    result = get_movie_from_db(query)
    parts = get_movie_parts(query)
    await state.clear()
    if result:
        file_id, movie_name = result
        wait_msg = await message.answer(TEXTS[lang]['loading'])
        await send_movie_to_user(message.chat.id, file_id, movie_name, query, message.from_user.id, lang)
        try:
            await wait_msg.delete()
        except:
            pass
        return
    if parts:
        parts_text = f"🎬 <b>{query}</b> — qismlar ({len(parts)} ta)\n\n"
        for pnum, _, pname, _ in parts:
            parts_text += f"  {pnum}. {pname}\n"
        parts_text += "\n👇 Qismni tanlang:"
        await message.answer(parts_text, reply_markup=get_parts_keyboard(query, parts, lang))
        return
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT code, name FROM movies WHERE LOWER(name) LIKE LOWER(%s) LIMIT 8", (f"%{message.text.strip()}%",))
        found = c.fetchall()
        conn.close()
    except:
        found = []
    if found:
        buttons = [[InlineKeyboardButton(text=f"🎬 {name} ({code})", callback_data=f"search_{code}")] for code, name in found]
        await message.answer("🔍 Topildi:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await message.answer("👇 Yoki boshqa amalni tanlang:", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(TEXTS[lang]['movie_not_found'], reply_markup=ReplyKeyboardRemove())

@dp.callback_query(F.data.startswith("search_"))
async def search_result_callback(callback_query: types.CallbackQuery):
    code = callback_query.data.replace("search_", "")
    user_id = callback_query.from_user.id
    lang = get_user_language(user_id) or "uz"
    result = get_movie_from_db(code)
    if result:
        file_id, movie_name = result
        await send_movie_to_user(user_id, file_id, movie_name, code, user_id, lang)
    await callback_query.answer()

# ==================== TOP KINOLAR USER ====================
@dp.message(F.text == "🔥 Top kinolar")
async def btn_top_user(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id) or "uz"
    if not await is_subscribed(user_id):
        not_sub = await get_not_subscribed_channels(user_id)
        await message.answer(TEXTS[lang]['not_subscribed_msg'], reply_markup=get_subscribe_keyboard_v2(lang, not_sub))
        return
    top = get_top_movies_for_users(limit=5)
    if not top:
        await message.answer("😕 Hozircha statistika yo'q.")
        return
    text = "🔥 <b>Eng ko'p ko'rilgan kinolar:</b>\n\n"
    buttons = []
    for i, (code, name, views) in enumerate(top, 1):
        text += f"{i}. 🎬 {name} — <b>{views}</b> marta ko'rilgan\n"
        buttons.append([InlineKeyboardButton(text=f"▶️ {i}. {name}", callback_data=f"search_{code}")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ==================== JANRLAR ====================
@dp.message(F.text == "🎭 Janrlar")
async def btn_genres(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id) or "uz"
    if not await is_subscribed(user_id):
        not_sub = await get_not_subscribed_channels(user_id)
        await message.answer(TEXTS[lang]['not_subscribed_msg'], reply_markup=get_subscribe_keyboard_v2(lang, not_sub))
        return
    genres_data = load_genres()
    if not genres_data:
        await message.answer("🎭 <b>Janrlar</b>\n\nHozircha janr bo'yicha kinolar yo'q.\n\nKino kodini yuboring yoki 🔍 Qidirish dan foydalaning!")
        return
    all_genres = set()
    for code, data in genres_data.items():
        genre = data.get("genre", "")
        if genre:
            all_genres.add(genre)
    if not all_genres:
        await message.answer("🎭 Hozircha janrlar bo'sh.")
        return
    buttons = []
    row = []
    for genre in sorted(all_genres):
        count = sum(1 for v in genres_data.values() if v.get("genre") == genre)
        row.append(InlineKeyboardButton(text=f"{genre} ({count})", callback_data=f"showgenre_{genre}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    await message.answer("🎭 <b>Janrni tanlang:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("showgenre_"))
async def show_genre_movies(callback_query: types.CallbackQuery):
    genre = callback_query.data.replace("showgenre_", "")
    genres_data = load_genres()
    movies_in_genre = [(code, data.get("name", code)) for code, data in genres_data.items() if data.get("genre") == genre]
    if not movies_in_genre:
        await callback_query.answer("Bu janrda kino yo'q.", show_alert=True)
        return
    text = f"{genre} <b>janridagi kinolar ({len(movies_in_genre)} ta):</b>\n\n"
    buttons = []
    for code, name in movies_in_genre[:20]:
        text += f"🎬 {name} (<code>{code}</code>)\n"
        buttons.append([InlineKeyboardButton(text=f"▶️ {name}", callback_data=f"search_{code}")])
    await callback_query.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback_query.answer()

# ==================== SEVIMLILAR BUTTON ====================
@dp.message(F.text == "⭐ Sevimlilar")
async def btn_favorites(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id) or "uz"
    if not await is_subscribed(user_id):
        not_sub = await get_not_subscribed_channels(user_id)
        await message.answer(TEXTS[lang]['not_subscribed_msg'], reply_markup=get_subscribe_keyboard_v2(lang, not_sub))
        return
    favs = get_user_favorites(user_id)
    if not favs:
        await message.answer("⭐ <b>Sevimlilarim</b>\n\nHozircha sevimlilar ro'yxatingiz bo'sh.\n\nKino yuklagandan so'ng <b>🤍 Sevimlilarga qo'sh</b> tugmasini bosing!")
        return
    text = f"⭐ <b>Sevimlilarim ({len(favs)} ta):</b>\n\n"
    buttons = []
    for i, (code, name, added_date) in enumerate(favs, 1):
        text += f"{i}. 🎬 {name} (<code>{code}</code>)\n"
        buttons.append([
            InlineKeyboardButton(text=f"▶️ {name}", callback_data=f"search_{code}"),
            InlineKeyboardButton(text="🗑", callback_data=f"unfav_{code}")
        ])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("unfav_"))
async def unfav_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    movie_code = callback_query.data.replace("unfav_", "")
    remove_from_favorites(user_id, movie_code)
    await callback_query.answer("🗑 O'chirildi.", show_alert=False)
    favs = get_user_favorites(user_id)
    if not favs:
        try:
            await callback_query.message.edit_text("⭐ Sevimlilar ro'yxatingiz bo'sh.")
        except:
            pass
        return
    text = f"⭐ <b>Sevimlilarim ({len(favs)} ta):</b>\n\n"
    buttons = []
    for i, (code, name, added_date) in enumerate(favs, 1):
        text += f"{i}. 🎬 {name} (<code>{code}</code>)\n"
        buttons.append([
            InlineKeyboardButton(text=f"▶️ {name}", callback_data=f"search_{code}"),
            InlineKeyboardButton(text="🗑", callback_data=f"unfav_{code}")
        ])
    try:
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except:
        pass

# ==================== PROFIL ====================


@dp.message(UserStates.writing_contact)
async def contact_message_handler(message: types.Message, state: FSMContext):
    if message.text and message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return
    user = message.from_user
    username_str = f"@{user.username}" if user.username else "yo'q"
    time_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg_type = "photo" if message.photo else "video" if message.video else "text"
    save_contact_message(user.id, user.username, user.first_name, message.text or f"[{msg_type}]", msg_type)
    header = (f"📩 <b>Yangi xabar (Aloqa)</b>\n━━━━━━━━━━━━\n"
              f"👤 {user.full_name}\n🆔 <code>{user.id}</code>\n"
              f"📎 {username_str}\n🕐 {time_str}\n━━━━━━━━━━━━\n💬 <b>Xabar:</b>")
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"reply_{user.id}"),
        InlineKeyboardButton(text="👤 Profil", callback_data=f"uinfo_{user.id}")
    ]])
    try:
        await bot.send_message(ADMIN_ID, header, parse_mode="HTML")
        await message.forward(ADMIN_ID)
        await bot.send_message(ADMIN_ID, "⬆️ Javob:", reply_markup=reply_kb)
    except Exception as e:
        print(f"❌ Admin ga yuborishda xato: {e}")
    await state.clear()
    await message.answer("✅ Xabaringiz adminga yuborildi! Tez orada javob olasiz.", reply_markup=ReplyKeyboardRemove())

# ==================== BUYURTMA ====================
@dp.message(F.text == "📬 Kino buyurtma berish")
async def btn_order_movie(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = get_user_language(user_id) or "uz"
    if not await is_subscribed(user_id):
        not_sub = await get_not_subscribed_channels(user_id)
        await message.answer(TEXTS[lang]['not_subscribed_msg'], reply_markup=get_subscribe_keyboard_v2(lang, not_sub))
        return
    await state.set_state(UserStates.writing_order)
    await message.answer(
        "📬 <b>Kino buyurtma berish</b>\n\n"
        "Qaysi kinoni istayotganingizni yozing:\n"
        "<i>Kino nomi, yili, aktyor va boshqa ma'lumotlarni yozsangiz tezroq topamiz!</i>",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]],
                                         resize_keyboard=True, one_time_keyboard=False)
    )

@dp.message(UserStates.writing_order)
async def process_order(message: types.Message, state: FSMContext):
    if message.text and message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return
    if not message.text:
        await message.answer("❌ Iltimos, matn yuboring.")
        return
    user = message.from_user
    order_id = save_film_order(user.id, user.username, user.first_name, message.text.strip())
    await state.clear()
    if order_id:
        await message.answer(
            f"✅ <b>Buyurtmangiz qabul qilindi! (#{order_id})</b>\n\n"
            "📬 Admin tez orada sizga javob beradi. Sabr qiling!",
            reply_markup=ReplyKeyboardRemove()
        )
        username_str = f"@{user.username}" if user.username else user.first_name
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="↩️ Javob", callback_data=f"reply_{user.id}"),
            InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"order_done_{order_id}")
        ]])
        try:
            await bot.send_message(ADMIN_ID,
                f"📬 <b>Yangi buyurtma #{order_id}</b>\n\n"
                f"👤 {user.full_name} ({username_str})\n🆔 <code>{user.id}</code>\n"
                f"📝 {message.text.strip()}\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                reply_markup=kb)
        except:
            pass
    else:
        await message.answer("❌ Xatolik yuz berdi. Qayta urinib ko'ring.", reply_markup=ReplyKeyboardRemove())

# ==================== ADMIN JAVOB ====================
@dp.callback_query(F.data.startswith("reply_"))
async def admin_reply_start(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    target_id = int(callback_query.data.replace("reply_", ""))
    await state.set_state(AdminStates.admin_reply_writing)
    await state.update_data(reply_target=target_id)
    await callback_query.message.answer(
        f"✍️ Foydalanuvchi <code>{target_id}</code> ga javob yozing:",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]],
                                         resize_keyboard=True, one_time_keyboard=False)
    )
    await callback_query.answer()

@dp.message(AdminStates.admin_reply_writing)
async def admin_reply_send(message: types.Message, state: FSMContext):
    if message.text and message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return
    data = await state.get_data()
    target_id = data.get("reply_target")
    await state.clear()
    try:
        await bot.send_message(target_id, "📨 <b>Adminden javob:</b>\n━━━━━━━━━━━━", parse_mode="HTML")
        await message.copy_to(target_id)
        await message.answer(f"✅ Javob <code>{target_id}</code> ga yuborildi.", parse_mode="HTML", reply_markup=get_admin_main_keyboard())
    except Exception as e:
        await message.answer(f"❌ Yuborib bo'lmadi: {e}", reply_markup=get_admin_main_keyboard())

@dp.callback_query(F.data.startswith("uinfo_"))
async def admin_view_user(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    user_id = int(callback_query.data.replace("uinfo_", ""))
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT username, first_name, last_name, subscribed, joined_date, last_active FROM users WHERE user_id=%s", (user_id,))
        row = c.fetchone()
        c.execute("SELECT COUNT(*) FROM movie_stats WHERE user_id=%s AND action='view'", (user_id,))
        watched = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM favorites WHERE user_id=%s", (user_id,))
        fav_count = c.fetchone()[0]
        conn.close()
    except:
        row = None; watched = 0; fav_count = 0
    if row:
        username, first, last, subscribed, joined, last_active = row
        text = (f"👤 <b>Foydalanuvchi</b>\n\n🆔 <code>{user_id}</code>\n"
                f"📛 {first or ''} {last or ''}\n👤 @{username or '—'}\n"
                f"✅ Obuna: {'Ha' if subscribed else 'Yoq'}\n"
                f"🎬 Ko'rgan: {watched} ta | ⭐ Sevimli: {fav_count} ta\n"
                f"📅 {joined.strftime('%d.%m.%Y') if joined else '—'}")
    else:
        text = f"<code>{user_id}</code> — topilmadi."
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"reply_{user_id}")]])
    await callback_query.message.answer(text, reply_markup=reply_kb, parse_mode="HTML")
    await callback_query.answer()

# ==================== ADMIN PANEL ====================
@dp.message(Command('admin'))
async def admin_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    stats = get_total_stats()
    notif = ""
    if stats.get('pending_orders', 0) > 0:
        notif += f"\n📬 {stats['pending_orders']} ta yangi buyurtma!"
    if stats.get('unanswered', 0) > 0:
        notif += f"\n💬 {stats['unanswered']} ta javob berilmagan xabar!"
    await message.answer(f"🛠️ <b>Admin paneli</b>{notif}", reply_markup=get_admin_main_keyboard())

@dp.message(Command('menu'))
async def menu_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    if user_id == ADMIN_ID:
        await message.answer("🛠️ Admin paneli:", reply_markup=get_admin_main_keyboard())
    else:
        lang = get_user_language(user_id) or "uz"
        await message.answer(TEXTS[lang]['welcome_back'], reply_markup=ReplyKeyboardRemove())

@dp.message(F.text == "🔧 Qo'shimcha buyruqlar")
async def show_extra_commands(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🔧 <b>Qo'shimcha buyruqlar:</b>", reply_markup=get_admin_extra_keyboard())

@dp.message(F.text == "🏠 Asosiy panel")
async def show_main_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await admin_start(message)

# ==================== BOT OBUNALARI (ADMIN) ====================
@dp.message(F.text == "🤖 Bot obunalari")
async def bot_subscriptions_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = "🤖 <b>Majburiy bot obunalari</b>\n\n"
    if BOT_SUBSCRIPTIONS:
        for i, bs in enumerate(BOT_SUBSCRIPTIONS, 1):
            uname = bs.get("username", "")
            link = bs.get("link", "")
            stats = get_bot_sub_stats(uname)
            text += (f"{i}. <b>{uname}</b>\n"
                     f"   🔗 {link}\n"
                     f"   👥 Jami: {stats['total']} | Bugun: {stats['today']} | Hafta: {stats['week']}\n\n")
    else:
        text += "Hozircha bot obunasi qo'shilmagan.\n\n"
    text += ("<b>Qanday ishlaydi?</b>\n"
             "• Foydalanuvchi botga /start bosadi → DB ga yoziladi\n"
             "• Sizning botingiz DB dan tekshiradi")
    await message.answer(text, reply_markup=get_bot_sub_manage_keyboard())

@dp.callback_query(F.data == "botsub_add")
async def botsub_add_start(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_bot_username)
    await callback_query.message.answer(
        "🤖 <b>Bot qo'shish</b>\n\nBot @username ini kiriting:\nMasalan: @myotherbot",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]],
                                         resize_keyboard=True, one_time_keyboard=False)
    )
    await callback_query.answer()

@dp.message(AdminStates.waiting_bot_username, F.text)
async def botsub_username_received(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_extra_keyboard())
        return
    username = message.text.strip()
    if not username.startswith("@"):
        username = "@" + username
    await state.update_data(bot_username=username)
    await state.set_state(AdminStates.waiting_bot_link)
    await message.answer(f"✅ Bot: <b>{username}</b>\n\n🔗 Botga havola kiriting:\nMasalan: https://t.me/{username.lstrip('@')}")

@dp.message(AdminStates.waiting_bot_link, F.text)
async def botsub_link_received(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_extra_keyboard())
        return
    link = message.text.strip()
    if not link.startswith("https://t.me/"):
        await state.clear()
        await message.answer("❌ Noto'g'ri havola! https://t.me/... bilan boshlanishi kerak.", reply_markup=get_admin_extra_keyboard())
        return
    data = await state.get_data()
    username = data["bot_username"]
    await state.clear()
    BOT_SUBSCRIPTIONS.append({"username": username, "link": link})
    save_bot_subscriptions(BOT_SUBSCRIPTIONS)
    await message.answer(f"✅ <b>Bot obunasi qo'shildi!</b>\n\n🤖 Bot: {username}\n🔗 Link: {link}", reply_markup=get_admin_extra_keyboard())

@dp.callback_query(F.data.startswith("botsub_del_"))
async def botsub_delete(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    idx = int(callback_query.data.replace("botsub_del_", ""))
    if 0 <= idx < len(BOT_SUBSCRIPTIONS):
        removed = BOT_SUBSCRIPTIONS.pop(idx)
        save_bot_subscriptions(BOT_SUBSCRIPTIONS)
        await callback_query.answer(f"✅ {removed.get('username')} o'chirildi.", show_alert=True)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=get_bot_sub_manage_keyboard())
        except:
            pass
    else:
        await callback_query.answer("❌ Topilmadi.", show_alert=True)

@dp.callback_query(F.data.startswith("botsub_info_"))
async def botsub_info(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    idx = int(callback_query.data.replace("botsub_info_", ""))
    if 0 <= idx < len(BOT_SUBSCRIPTIONS):
        bs = BOT_SUBSCRIPTIONS[idx]
        uname = bs.get("username", "")
        stats = get_bot_sub_stats(uname)
        await callback_query.answer(f"🤖 {uname}\n👥 Jami: {stats['total']}\nBugun: {stats['today']}\nHafta: {stats['week']}", show_alert=True)
    else:
        await callback_query.answer("❌ Topilmadi.", show_alert=True)

# ==================== KINO QO'SHISH (ADMIN) ====================
@dp.message(F.text == "🎬 Kino qo'shish")
@dp.message(Command('add'))
async def add_movie_step1(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo'shish", callback_data="add_single")],
        [InlineKeyboardButton(text="📺 Serial qo'shish", callback_data="add_multi")]
    ])
    await message.answer("Qanday turdagi kontent qo'shmoqchisiz?", reply_markup=builder)

@dp.callback_query(F.data == "add_single")
async def add_single_movie(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_movie_file)
    await callback_query.message.edit_text("🎬 Kino faylini (video) yuboring:")
    await callback_query.answer()

@dp.callback_query(F.data == "add_multi")
async def add_multi_movie(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_part_code)
    await callback_query.message.edit_text(
        "📺 <b>Serial qo'shish</b>\n\n"
        "Serial kodini kiriting:\n"
        "<i>Masalan: AVATAR, SQUIDGAME, S01</i>"
    )
    await callback_query.answer()

@dp.message(AdminStates.waiting_for_movie_file, F.video)
async def add_movie_step2(message: types.Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await state.set_state(AdminStates.waiting_for_movie_code)
    await message.answer("🔢 Kino kodini kiriting (masalan: M123):")

@dp.message(AdminStates.waiting_for_movie_code, F.text)
async def add_movie_step3(message: types.Message, state: FSMContext):
    await state.update_data(movie_code=message.text.strip().upper())
    await state.set_state(AdminStates.waiting_for_movie_name)
    await message.answer("📝 Kino nomini kiriting:")

@dp.message(AdminStates.waiting_for_movie_name, F.text)
async def add_movie_step4(message: types.Message, state: FSMContext):
    movie_name = " ".join(message.text.strip().split())
    data = await state.get_data()
    if add_movie_to_db(data['movie_code'], data['file_id'], movie_name):
        await message.answer(
            f"✅ Kino qo'shildi!\n"
            f"🔢 Kod: <code>{data['movie_code']}</code>\n"
            f"📛 Nomi: {movie_name}\n\n"
            f"🎭 Ushbu kinoga janr belgilaysizmi?",
            reply_markup=get_genre_keyboard(data['movie_code'])
        )
        current_genres = load_genres()
        current_genres[data['movie_code']] = {"name": movie_name, "genre": ""}
        save_genres(current_genres)
        MOVIE_GENRES.update(current_genres)
    else:
        await message.answer(f"❌ <code>{data['movie_code']}</code> kodi allaqachon mavjud!")
        await state.set_state(AdminStates.waiting_for_movie_code)
        return
    await state.clear()

@dp.callback_query((F.data.startswith("genre_skip_") | F.data.startswith("genre_skip|")))
async def genre_skip_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    movie_code = callback_query.data.split("|")[1] if "|" in callback_query.data else callback_query.data.replace("genre_skip_", "").replace("genre_skip|", "")
    try:
        await callback_query.message.edit_text(
            f"⏭ Janr o'tkazib yuborildi.\n\n🔗 <code>{movie_code}</code> kinosi uchun qo'shimcha tugma qo'shish?",
            reply_markup=get_add_btn_keyboard(movie_code)
        )
    except:
        pass
    await callback_query.answer()

@dp.callback_query((F.data.startswith("genre_") | F.data.startswith("genre|")) & ~(F.data.startswith("genre_skip_") | F.data.startswith("genre_skip|")))
async def genre_select_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    raw = callback_query.data
    if "|" in raw:
        parts = raw.split("|", 2)
        if len(parts) < 3:
            await callback_query.answer("Xatolik.", show_alert=True)
            return
        movie_code = parts[1]
        genre = parts[2]
    else:
        parts = raw.replace("genre_", "", 1).split("_", 1)
        if len(parts) < 2:
            await callback_query.answer("Xatolik.", show_alert=True)
            return
        movie_code = parts[0]
        genre = parts[1]
    genres_data = load_genres()
    if movie_code not in genres_data:
        result = get_movie_from_db(movie_code)
        movie_name = result[1] if result else movie_code
        genres_data[movie_code] = {"name": movie_name, "genre": genre}
    else:
        genres_data[movie_code]["genre"] = genre
    save_genres(genres_data)
    try:
        await callback_query.message.edit_text(
            f"✅ Janr belgilandi: {genre}\n\n🔗 <code>{movie_code}</code> kinosi uchun qo'shimcha tugma qo'shish?",
            reply_markup=get_add_btn_keyboard(movie_code)
        )
    except:
        pass
    await callback_query.answer(f"✅ {genre} saqlandi!")

@dp.callback_query(F.data.startswith("addbtn_no_"))
async def addbtn_no_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    movie_code = callback_query.data.replace("addbtn_no_", "")
    try:
        await callback_query.message.edit_text(f"✅ <code>{movie_code}</code> kino tayyor!")
    except:
        pass
    await callback_query.answer()

@dp.callback_query(F.data.startswith("addbtn_yes_"))
async def addbtn_yes_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    movie_code = callback_query.data.replace("addbtn_yes_", "")
    await state.update_data(btn_target=movie_code)
    await state.set_state(AdminStates.inline_add_btn_text)
    try:
        await callback_query.message.edit_text(f"🔗 <code>{movie_code}</code> uchun tugma matni:\n\nMasalan: 📢 Kanalimiz")
    except:
        pass
    await callback_query.answer()

@dp.message(AdminStates.inline_add_btn_text, F.text)
async def inline_add_btn_text_received(message: types.Message, state: FSMContext):
    if message.text and message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return
    await state.update_data(btn_text=message.text.strip())
    await state.set_state(AdminStates.inline_add_btn_url)
    await message.answer("🔗 Tugma havolasini kiriting:\nMasalan: https://t.me/relaxkinoo")

@dp.message(AdminStates.inline_add_btn_url, F.text)
async def inline_add_btn_url_received(message: types.Message, state: FSMContext):
    if message.text and message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return
    url = message.text.strip()
    if not url.startswith('http'):
        await message.answer("❌ Havola http:// yoki https:// bilan boshlanishi kerak.")
        return
    data = await state.get_data()
    target = data['btn_target']
    btn_text = data['btn_text']
    if target not in ADD_BUTTONS:
        ADD_BUTTONS[target] = []
    ADD_BUTTONS[target].append({"text": btn_text, "url": url})
    save_add_buttons(ADD_BUTTONS)
    await state.clear()
    await message.answer(f"✅ Tugma qo'shildi!\n\nMatn: {btn_text}\nHavola: {url}\n\n🎬 <code>{target}</code> kinosi tayyor!", reply_markup=get_admin_main_keyboard())

# ==================== KINO O'CHIRISH (ADMIN) ====================
@dp.message(F.text == "🗑️ Kino o'chirish")
@dp.message(Command('delete'))
async def delete_movie_step1(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_delete_code)
    await message.answer("🗑️ O'chirmoqchi bo'lgan kinoning kodini kiriting:")

@dp.message(AdminStates.waiting_for_delete_code, F.text)
async def delete_movie_step2(message: types.Message, state: FSMContext):
    movie_code = message.text.strip().upper()
    if delete_movie_from_db(movie_code):
        await message.answer(f"✅ {movie_code} o'chirildi!")
    else:
        await message.answer(f"❌ {movie_code} topilmadi.")
    await state.clear()
    await admin_start(message)

@dp.message(F.text == "⚠️ Hammasini o'chir")
@dp.message(Command('clearall'))
async def clear_all_movies_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚠️ Ha, hammasini o'chir", callback_data="confirm_clearall"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_clearall")
    ]])
    await message.answer("⚠️ Barcha kinolarni o'chirishni tasdiqlaysizmi?", reply_markup=kb)

@dp.callback_query(F.data == "confirm_clearall")
async def confirm_clearall(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    count = clear_all_movies()
    await callback_query.message.edit_text(f"✅ {count} ta kino o'chirildi.")
    await callback_query.answer()

@dp.callback_query(F.data == "cancel_clearall")
async def cancel_clearall(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("❌ Bekor qilindi.")
    await callback_query.answer()

@dp.message(F.text == "📋 Kinolar ro'yxati")
@dp.message(Command('list'))
async def list_movies(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    movies = get_all_movies()
    parts_list = get_all_parts_list()
    text = ""
    if movies:
        text += f"🎬 <b>Oddiy kinolar ({len(movies)} ta):</b>\n"
        text += "\n".join([f"<code>{code}</code> — {name}" for code, name in movies]) + "\n\n"
    if parts_list:
        text += f"🎬🎬 <b>Ko'p qismli ({len(parts_list)} ta):</b>\n"
        for code, count, parts in parts_list:
            text += f"<code>{code}</code> — {count} qism\n"
    if not text:
        text = "ℹ️ Hozircha kino mavjud emas."
    await message.answer(text[:4000])

@dp.message(F.text == "📊 Statistika")
@dp.message(Command('stat'))
async def get_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    s = get_total_stats()
    top = s.get('top_movie')
    top_str = f"\n\n🏆 Eng ko'p: <b>{top[1]}</b> ({top[0]}) — {top[2]} marta" if top else ""
    bot_subs_str = f"\n🤖 Bot obuna: {len(BOT_SUBSCRIPTIONS)} ta" if BOT_SUBSCRIPTIONS else ""
    text = (
        f"📊 <b>Bot statistikasi</b>\n━━━━━━━━━━━━\n"
        f"👥 Jami: <b>{s.get('total_users',0)}</b> | Bugun yangi: <b>{s.get('today_new',0)}</b>\n"
        f"🚫 Bot bloklaganlar: <b>{s.get('blocked_users',0)}</b>\n"
        f"🟢 Bugun faol: <b>{s.get('active_today',0)}</b> | Obuna: <b>{s.get('subscribed',0)}</b>\n\n"
        f"🎬 Kinolar: <b>{s.get('movie_count',0)}</b> | Serial: <b>{s.get('series_count',0)}</b>\n\n"
        f"👁 Ko'rishlar:\n"
        f"├─ Bugun: <b>{s.get('today_views',0)}</b>\n"
        f"├─ Hafta: <b>{s.get('week_views',0)}</b>\n"
        f"├─ Oy: <b>{s.get('month_views',0)}</b>\n"
        f"└─ Jami: <b>{s.get('total_views',0)}</b>\n\n"
        f"🔗 Ochiq: {', '.join(CHANNELS) if CHANNELS else 'yoq'}\n"
        f"🔒 Yopiq: {', '.join(PRIVATE_CHANNELS) if PRIVATE_CHANNELS else 'yoq'}"
        f"{bot_subs_str}{top_str}"
    )
    if s.get('pending_orders', 0) > 0:
        text += f"\n\n📬 Kutilayotgan buyurtmalar: <b>{s['pending_orders']}</b> ta"
    if s.get('unanswered', 0) > 0:
        text += f"\n💬 Javob berilmagan: <b>{s['unanswered']}</b> ta"
    await message.answer(text)

@dp.message(F.text == "👥 Foydalanuvchilar")
@dp.message(Command('users'))
async def list_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    s = get_total_stats()
    all_users = get_all_users()
    active = get_active_users()
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT user_id, username, first_name FROM users
                     WHERE is_blocked_bot=TRUE ORDER BY joined_date DESC LIMIT 20""")
        blocked_list = c.fetchall()
        conn.close()
    except:
        blocked_list = []
    text = (f"👥 <b>Foydalanuvchilar</b>\n\n"
            f"📊 Jami: <b>{len(all_users)}</b> ta\n"
            f"✅ Faol: <b>{len(active)}</b> ta\n"
            f"🚫 Bloklaganlar: <b>{s.get('blocked_users',0)}</b> ta\n"
            f"📅 Bugun yangi: <b>{s.get('today_new',0)}</b> ta\n"
            f"🟢 Bugun faol: <b>{s.get('active_today',0)}</b> ta\n"
            f"📋 Obunali: <b>{s.get('subscribed',0)}</b> ta\n")
    if blocked_list:
        text += f"\n🚫 <b>So'nggi bloklaganlar ({len(blocked_list)} ta):</b>\n"
        for uid, username, first_name in blocked_list:
            if username:
                text += f"  • @{username} (<code>{uid}</code>)\n"
            elif first_name:
                text += f"  • {first_name} (<code>{uid}</code>)\n"
            else:
                text += f"  • <code>{uid}</code>\n"
    await message.answer(text[:4000])

# ==================== REKLAMA YUBORISH ====================
@dp.message(F.text == "📢 Reklama yuborish")
@dp.message(Command('reklama'))
async def start_advertisement(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    all_users = get_all_users()
    active_users = get_active_users()
    real_active = active_users if active_users else all_users
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Oddiy reklama", callback_data="ad_standard")],
        [InlineKeyboardButton(text="🔗 Add buttons bilan reklama", callback_data="ad_with_buttons")],
    ])
    await message.answer(
        f"📢 <b>Reklama yuborish</b>\n\n"
        f"👥 Jami: <b>{len(all_users)}</b> ta\n"
        f"✅ Faol: <b>{len(real_active)}</b> ta\n\n"
        f"Reklama turini tanlang:",
        reply_markup=kb
    )

@dp.callback_query(F.data == "ad_standard")
async def ad_standard_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_for_advertisement)
    await state.update_data(ad_extra_buttons=[])
    await callback_query.message.answer(
        "📨 <b>Oddiy reklama</b>\n\n"
        "Reklama xabarini yuboring:\n"
        "<i>Matn, rasm, video, audio — istalgan format</i>"
    )
    await callback_query.answer()

@dp.callback_query(F.data == "ad_with_buttons")
async def ad_with_buttons_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_ad_buttons)
    await state.update_data(ad_extra_buttons=[])
    await callback_query.message.answer(
        "🔗 <b>Add buttons qo'shish</b>\n\n"
        "Tugma ma'lumotini yuboring:\n"
        "<code>Tugma matni | https://havola.uz</code>\n\n"
        "<i>Bir necha tugma uchun har birini yangi qatorga yozing</i>\n\n"
        "Tugatgach <b>✅ Tayyor</b> bosing.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✅ Tayyor")]],
            resize_keyboard=True
        )
    )
    await callback_query.answer()

@dp.message(AdminStates.waiting_ad_buttons, F.text == "✅ Tayyor")
async def ad_buttons_done(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_advertisement)
    data = await state.get_data()
    btns = data.get("ad_extra_buttons", [])
    btn_info = f"\n✅ {len(btns)} ta tugma qo'shildi" if btns else "\n⚠️ Hali tugma qo'shilmadi"
    await message.answer(
        f"📨 <b>Reklama xabarini yuboring:</b>{btn_info}\n\n"
        "<i>Matn, rasm, video, audio — istalgan format</i>"
    )

@dp.message(AdminStates.waiting_ad_buttons, F.text)
async def ad_buttons_add(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return
    data = await state.get_data()
    btns = data.get("ad_extra_buttons", [])
    added = 0
    for line in message.text.strip().split("\n"):
        line = line.strip()
        if "|" in line:
            parts = line.split("|", 1)
            text = parts[0].strip()
            url = parts[1].strip()
            if text and url.startswith("http"):
                btns.append({"text": text, "url": url})
                added += 1
    await state.update_data(ad_extra_buttons=btns)
    await message.answer(
        f"✅ {added} ta tugma qo'shildi. Jami: {len(btns)} ta\n\n"
        f"Yana qo'shish uchun yuboring yoki <b>✅ Tayyor</b> bosing."
    )

# ==================== BROADCAST TIZIMI ====================
BROADCAST_WORKERS = 25
BROADCAST_RATE = 0.04
BROADCAST_RETRIES = 3

async def _broadcast_worker(
    worker_id: int,
    queue: asyncio.Queue,
    src_message: types.Message,
    extra_buttons: list,
    stats: dict,
):
    while True:
        try:
            uid = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        for attempt in range(BROADCAST_RETRIES):
            try:
                if extra_buttons:
                    rows = []
                    for i in range(0, len(extra_buttons), 2):
                        row = []
                        for btn in extra_buttons[i:i+2]:
                            row.append(InlineKeyboardButton(
                                text=btn["text"], url=btn["url"]
                            ))
                        rows.append(row)
                    kb = InlineKeyboardMarkup(inline_keyboard=rows)
                    await src_message.copy_to(uid, reply_markup=kb)
                else:
                    await src_message.copy_to(uid)

                stats["sent"] += 1
                break

            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ["blocked by user", "bot was blocked", "user is deactivated", "chat write forbidden", "have no rights to send", "forbidden"]):
                    mark_user_blocked_bot(uid)
                    stats["blocked"] += 1
                    broadcast_logger.warning(f"[W{worker_id}] BLOCKED uid={uid}")
                    break
                elif any(x in err for x in ["chat not found", "user not found", "peer_id_invalid", "chat_id_invalid", "input_user_deactivated"]):
                    stats["deleted"] += 1
                    broadcast_logger.warning(f"[W{worker_id}] DELETED uid={uid}")
                    break
                elif any(x in err for x in ["too many requests", "flood", "retry after", "429"]):
                    wait_time = 30
                    try:
                        m = re.search(r'retry after (\d+)', err)
                        if m:
                            wait_time = int(m.group(1)) + 3
                    except:
                        pass
                    stats["flood"] += 1
                    broadcast_logger.warning(f"[W{worker_id}] FLOOD wait={wait_time}s uid={uid}")
                    await asyncio.sleep(wait_time)
                elif any(x in err for x in ["timeout", "network", "connection", "server disconnected", "timedout", "aiohttp"]):
                    wait = 2.0 * (attempt + 1)
                    broadcast_logger.warning(f"[W{worker_id}] NETWORK attempt={attempt+1} uid={uid}")
                    if attempt < BROADCAST_RETRIES - 1:
                        await asyncio.sleep(wait)
                    else:
                        stats["failed"] += 1
                        break
                else:
                    broadcast_logger.error(f"[W{worker_id}] UNKNOWN uid={uid}: {err[:80]}")
                    if attempt < BROADCAST_RETRIES - 1:
                        await asyncio.sleep(1.0)
                    else:
                        stats["failed"] += 1
                        break

        await asyncio.sleep(BROADCAST_RATE)
        queue.task_done()

@dp.message(AdminStates.waiting_for_advertisement)
async def send_advertisement(message: types.Message, state: FSMContext):
    data = await state.get_data()
    extra_buttons = data.get("ad_extra_buttons", [])
    await state.clear()

    users = get_active_users()
    if not users:
        users = get_all_users()
    if not users:
        await message.answer("❌ Hech qanday foydalanuvchi yo'q!")
        return

    total = len(users)

    msg_type = (
        "photo" if message.photo else
        "video" if message.video else
        "audio" if message.audio else
        "document" if message.document else
        "text"
    )
    ad_id = add_advertisement_to_db(
        message_id=message.message_id,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        message_type=msg_type
    )

    stats = {"sent": 0, "blocked": 0, "deleted": 0, "flood": 0, "failed": 0}

    queue = asyncio.Queue()
    for uid in users:
        await queue.put(uid)

    btn_info = f" | 🔗 {len(extra_buttons)} tugma" if extra_buttons else ""
    start_time = datetime.now()
    progress_msg = await message.answer(
        f"📤 <b>Reklama boshlandi</b>{btn_info}\n\n"
        f"👥 Jami: <b>{total}</b> ta\n"
        f"⚡ Workerlar: <b>{BROADCAST_WORKERS}</b> ta\n"
        f"⏳ Taxminiy: ~{max(1, total // BROADCAST_WORKERS)} soniya"
    )

    async def update_progress():
        last_sent = 0
        while not queue.empty() or stats["sent"] + stats["blocked"] + stats["deleted"] + stats["failed"] < total:
            await asyncio.sleep(5)
            done = stats["sent"] + stats["blocked"] + stats["deleted"] + stats["failed"]
            if done == last_sent:
                continue
            last_sent = done
            elapsed = max(1, int((datetime.now() - start_time).total_seconds()))
            speed = done / elapsed if elapsed > 0 else 0
            remaining = total - done
            eta = int(remaining / speed) if speed > 0 else 0
            percent = done * 100 // total if total > 0 else 0
            try:
                await progress_msg.edit_text(
                    f"📤 <b>Reklama yuborilmoqda...</b>\n\n"
                    f"✅ Yuborildi:   <b>{stats['sent']}</b>\n"
                    f"🚫 Bloklagan:  <b>{stats['blocked']}</b>\n"
                    f"🗑 Topilmadi:  <b>{stats['deleted']}</b>\n"
                    f"⚡ Flood:       <b>{stats['flood']}</b>\n"
                    f"❌ Xato:        <b>{stats['failed']}</b>\n\n"
                    f"📊 {done}/{total} ({percent}%)\n"
                    f"⏱ O'tdi: {elapsed}s | Qoldi: ~{eta}s\n"
                    f"🚀 {speed:.1f} yuborildi/s"
                )
            except:
                pass

    worker_tasks = [
        asyncio.create_task(
            _broadcast_worker(i, queue, message, extra_buttons, stats)
        )
        for i in range(BROADCAST_WORKERS)
    ]
    progress_task = asyncio.create_task(update_progress())

    await asyncio.gather(*worker_tasks)
    progress_task.cancel()
    try:
        await progress_task
    except asyncio.CancelledError:
        pass

    total_elapsed = max(1, int((datetime.now() - start_time).total_seconds()))
    delivery_rate = (stats["sent"] / total * 100) if total > 0 else 0
    final_text = (
        f"✅ <b>Reklama yakunlandi!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"✅ Yuborildi:    <b>{stats['sent']}</b>\n"
        f"🚫 Bloklagan:   <b>{stats['blocked']}</b>\n"
        f"🗑 Topilmadi:   <b>{stats['deleted']}</b>\n"
        f"⚡ Flood:        <b>{stats['flood']}</b>\n"
        f"❌ Xato:         <b>{stats['failed']}</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👥 Jami: <b>{total}</b>\n"
        f"📈 Yetkazish: <b>{delivery_rate:.1f}%</b>\n"
        f"⏱ Vaqt: <b>{total_elapsed}s</b>"
        f" (~{total_elapsed//60}:{total_elapsed%60:02d})"
    )
    if ad_id:
        final_text += f"\n🆔 Reklama: <b>#{ad_id}</b>"
    try:
        await progress_msg.edit_text(final_text)
    except:
        await message.answer(final_text)

# ==================== QOLGAN ADMIN FUNKSIYALAR (QISQARTIRILGAN) ====================
@dp.message(F.text == "📋 Reklamalar ro'yxati")
@dp.message(Command('reklamalar'))
async def list_advertisements(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    ads = get_all_sent_advertisements()
    if not ads:
        await message.answer("ℹ️ Hech qanday reklama yuborilmagan.")
        return
    text = f"📋 <b>Reklamalar ro'yxati ({len(ads)} ta):</b>\n\n"
    buttons = []
    type_emoji = {"text": "📝", "photo": "🖼", "video": "🎬", "audio": "🎵", "document": "📎"}
    for ad in ads[:15]:
        ad_id, msg_id, uid, username, first_name, msg_type, sent_date, is_deleted, chat_id = ad
        uinfo = f"@{username}" if username else (first_name or f"id:{uid}")
        status = "❌ O'chirilgan" if is_deleted else "✅ Faol"
        date_str = sent_date.strftime("%d.%m.%Y %H:%M") if sent_date else "—"
        emoji = type_emoji.get(msg_type, "📨")
        text += f"{emoji} <b>#{ad_id}</b> | {uinfo}\n📅 {date_str} | {status}\n──────────────\n"
        if not is_deleted:
            buttons.append([InlineKeyboardButton(text=f"🗑 #{ad_id} reklamani o'chirish", callback_data=f"del_ad_{ad_id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await message.answer(text[:4000], reply_markup=kb)

@dp.callback_query(F.data.startswith("del_ad_"))
async def del_ad_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    ad_id = int(callback_query.data.replace("del_ad_", ""))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chir", callback_data=f"confirm_delete_{ad_id}"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_delete")
    ]])
    await callback_query.message.answer(f"⚠️ <b>#{ad_id} reklamani o'chirishni tasdiqlaysizmi?</b>\n\nBarcha foydalanuvchilardagi xabar o'chiriladi.", reply_markup=kb)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_ad(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    ad_id = int(callback_query.data.replace("confirm_delete_", ""))
    progress = await callback_query.message.answer(f"🔄 <b>#{ad_id} reklama o'chirilmoqda...</b>\n⏳ Kutib turing...")
    success, count = await delete_advertisement_completely(ad_id)
    if success:
        await progress.edit_text(f"✅ <b>Reklama #{ad_id} o'chirildi!</b>\n\n🗑 {count} ta foydalanuvchidan xabar o'chirildi.")
    else:
        await progress.edit_text(f"❌ Reklama #{ad_id} topilmadi yoki allaqachon o'chirilgan.")
    try:
        await callback_query.message.delete()
    except:
        pass
    await callback_query.answer()

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback_query: types.CallbackQuery):
    try:
        await callback_query.message.delete()
    except:
        pass
    await callback_query.answer("❌ Bekor qilindi.")

async def delete_advertisement_completely(ad_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT message_id, chat_id FROM advertisements WHERE id=%s AND is_deleted=FALSE", (ad_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return False, 0
        original_msg_id, source_chat_id = row
        users = get_active_users()
        deleted_count = 0
        for uid in users:
            try:
                await bot.delete_message(chat_id=uid, message_id=original_msg_id)
                deleted_count += 1
            except:
                pass
            await asyncio.sleep(0.05)
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE advertisements SET is_deleted=TRUE WHERE id=%s", (ad_id,))
        conn.commit()
        conn.close()
        broadcast_logger.info(f"Ad #{ad_id} deleted from {deleted_count} users")
        return True, deleted_count
    except Exception as e:
        broadcast_logger.error(f"delete_advertisement_completely ad_id={ad_id}: {e}")
        return False, 0

# ==================== KANAL BOSHQARUVI ====================
@dp.message(F.text == "📡 Kanallar ro'yxati")
@dp.message(Command('channels'))
async def list_channels(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = "📡 <b>Kanallar:</b>\n\n"
    if CHANNELS:
        text += "🔓 <b>Ochiq kanallar:</b>\n"
        for i, (ch, link) in enumerate(zip(CHANNELS, CHANNEL_LINKS), 1):
            text += f"{i}. {ch} — {link}\n"
    if PRIVATE_CHANNELS:
        text += "\n🔒 <b>Yopiq kanallar:</b>\n"
        for i, (ch, link) in enumerate(zip(PRIVATE_CHANNELS, PRIVATE_LINKS), 1):
            text += f"{i}. {ch} — {link}\n"
    if BOT_SUBSCRIPTIONS:
        text += "\n🤖 <b>Bot obunalari:</b>\n"
        for i, bs in enumerate(BOT_SUBSCRIPTIONS, 1):
            text += f"{i}. {bs.get('username')} — {bs.get('link')}\n"
    if not CHANNELS and not PRIVATE_CHANNELS and not BOT_SUBSCRIPTIONS:
        text += "Hozircha kanal yo'q."
    await message.answer(text)

@dp.message(F.text == "➕ Kanal qo'shish")
@dp.message(Command('addchannel'))
async def add_channel_step1(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_channel_username)
    await message.answer("➕ Kanal username'ini yuboring:\nMasalan: @relaxkinoo\n\n<i>Bot kanalda admin bo'lishi kerak!</i>")

@dp.message(AdminStates.waiting_for_channel_username, F.text)
async def add_channel_step2(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    if not ch.startswith('@'):
        ch = '@' + ch
    try:
        await bot.get_chat_member(ch, message.from_user.id)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
        await state.clear()
        return
    if ch in CHANNELS:
        await message.answer(f"❌ {ch} allaqachon ro'yxatda!")
        await state.clear()
        return
    await state.update_data(channel_username=ch)
    await state.set_state(AdminStates.waiting_for_channel_link)
    await message.answer(f"✅ {ch}\n\nKanal havolasini yuboring:\nhttps://t.me/{ch.replace('@','')}")

@dp.message(AdminStates.waiting_for_channel_link, F.text)
async def add_channel_step3(message: types.Message, state: FSMContext):
    link = message.text.strip()
    data = await state.get_data()
    if not link.startswith('https://t.me/'):
        await message.answer("❌ Link https://t.me/... bo'lishi kerak.")
        return
    CHANNELS.append(data['channel_username'])
    CHANNEL_LINKS.append(link)
    save_channels(CHANNELS, CHANNEL_LINKS, PRIVATE_CHANNELS, PRIVATE_LINKS)
    await message.answer(f"✅ Kanal qo'shildi: {data['channel_username']}\nJami: {len(CHANNELS)} ta")
    await state.clear()

@dp.message(F.text == "🔒 Yopiq kanal qo'shish")
async def add_private_channel_btn(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_private_channel)
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]], resize_keyboard=True, one_time_keyboard=False)
    await message.answer(
        "🔒 <b>Yopiq kanal qo'shish</b>\n\n"
        "Kanal ID sini kiriting (masalan: -1001234567890):\n"
        "<i>ID ni @userinfobot dan olishingiz mumkin</i>\n\n"
        "<b>MUHIM:</b> Faqat raqamli ID kiriting!",
        reply_markup=cancel_kb
    )

@dp.message(AdminStates.waiting_private_channel, F.text)
async def add_private_channel_id(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_extra_keyboard())
        return
    ch = message.text.strip()
    await state.update_data(private_channel=ch)
    await state.set_state(AdminStates.waiting_private_link)
    await message.answer(f"🔗 <b>{ch}</b> uchun invite havolani yuboring:\nMasalan: https://t.me/+xxxxxxxxxx\n\n<i>Bekor qilish uchun ❌ Bekor bosing</i>")

@dp.message(AdminStates.waiting_private_link, F.text)
async def add_private_channel_link(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_extra_keyboard())
        return
    link = message.text.strip()
    data = await state.get_data()
    if not link.startswith('https://t.me/'):
        await message.answer("❌ Link <b>https://t.me/...</b> bilan boshlanishi kerak!\nQaytadan yuboring yoki ❌ Bekor bosing.")
        return
    ch = data['private_channel']
    if ch not in PRIVATE_CHANNELS:
        PRIVATE_CHANNELS.append(ch)
        PRIVATE_LINKS.append(link)
        save_channels(CHANNELS, CHANNEL_LINKS, PRIVATE_CHANNELS, PRIVATE_LINKS)
        await message.answer(f"✅ Yopiq kanal qo'shildi!\n\n📢 Kanal ID: {ch}\n🔗 Link: {link}\n\nJami yopiq kanallar: {len(PRIVATE_CHANNELS)} ta", reply_markup=get_admin_extra_keyboard())
    else:
        await message.answer(f"❌ {ch} allaqachon ro'yxatda!", reply_markup=get_admin_extra_keyboard())
    await state.clear()

@dp.message(F.text == "➖ Kanal o'chirish")
@dp.message(Command('removechannel'))
async def remove_channel_step1(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not CHANNELS and not PRIVATE_CHANNELS:
        await message.answer("ℹ️ Kanal yo'q.")
        return
    lines = []
    for i, ch in enumerate(CHANNELS, 1):
        lines.append(f"{i}. 🔓 {ch}")
    for i, ch in enumerate(PRIVATE_CHANNELS, len(CHANNELS) + 1):
        lines.append(f"{i}. 🔒 {ch} (yopiq)")
    await state.set_state(AdminStates.waiting_for_delete_channel)
    await message.answer("➖ O'chirish uchun raqamini kiriting:\n\n" + "\n".join(lines))

@dp.message(AdminStates.waiting_for_delete_channel, F.text)
async def remove_channel_step2(message: types.Message, state: FSMContext):
    try:
        num = int(message.text.strip())
        total_open = len(CHANNELS)
        if 1 <= num <= total_open:
            removed = CHANNELS.pop(num - 1)
            CHANNEL_LINKS.pop(num - 1)
            save_channels(CHANNELS, CHANNEL_LINKS, PRIVATE_CHANNELS, PRIVATE_LINKS)
            await message.answer(f"✅ O'chirildi: {removed}")
        elif total_open < num <= total_open + len(PRIVATE_CHANNELS):
            idx = num - total_open - 1
            removed = PRIVATE_CHANNELS.pop(idx)
            PRIVATE_LINKS.pop(idx)
            save_channels(CHANNELS, CHANNEL_LINKS, PRIVATE_CHANNELS, PRIVATE_LINKS)
            await message.answer(f"✅ O'chirildi: {removed}")
        else:
            await message.answer("❌ Noto'g'ri raqam.")
    except ValueError:
        await message.answer("❌ Raqam kiriting!")
    await state.clear()

# ==================== QOLGAN ADMIN FUNKSIYALAR (ADD BUTTONS, TOP, STATS, TEST, BLOCK, ORDERS) ====================
@dp.message(F.text == "🔗 Add buttons boshqaruv")
async def add_buttons_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    global_btns = ADD_BUTTONS.get("_global", [])
    all_movie_btns = {k: v for k, v in ADD_BUTTONS.items() if k != "_global" and v}
    text = "🔗 <b>Add Buttons boshqaruvi</b>\n\n"
    text += f"🌐 <b>Global tugmalar:</b> {len(global_btns)} ta\n"
    for i, btn in enumerate(global_btns, 1):
        text += f"  {i}. {btn['text']} — {btn['url']}\n"
    if all_movie_btns:
        text += f"\n🎬 <b>Kino-spesifik tugmalar:</b>\n"
        for movie_code, btns in all_movie_btns.items():
            text += f"  <code>{movie_code}</code>: {len(btns)} ta\n"
    await message.answer(text, reply_markup=get_add_buttons_list_keyboard())

@dp.callback_query(F.data == "addbtn_global_new")
async def addbtn_global_new(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await state.update_data(btn_target="_global")
    await state.set_state(AdminStates.new_btn_text)
    await callback_query.message.answer("🌐 Global tugma matni:\nMasalan: 📢 Kanalimiz")
    await callback_query.answer()

@dp.callback_query(F.data == "addbtn_movie_new")
async def addbtn_movie_new(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.new_btn_movie_code)
    await callback_query.message.answer("🎬 Kino kodini kiriting:\nMasalan: M123")
    await callback_query.answer()

@dp.message(AdminStates.new_btn_movie_code, F.text)
async def new_btn_movie_code_received(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(btn_target=code)
    await state.set_state(AdminStates.new_btn_text)
    await message.answer(f"✅ Kino: <code>{code}</code>\n\nTugma matni:")

@dp.message(AdminStates.new_btn_text, F.text)
async def new_btn_text_received(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_extra_keyboard())
        return
    await state.update_data(btn_text=message.text.strip())
    await state.set_state(AdminStates.new_btn_url)
    await message.answer("🔗 Tugma havolasi:\nMasalan: https://t.me/relaxkinoo")

@dp.message(AdminStates.new_btn_url, F.text)
async def new_btn_url_received(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_extra_keyboard())
        return
    url = message.text.strip()
    if not url.startswith('http'):
        await message.answer("❌ Havola http:// yoki https:// bilan boshlanishi kerak.")
        return
    data = await state.get_data()
    target = data['btn_target']
    btn_text = data['btn_text']
    if target not in ADD_BUTTONS:
        ADD_BUTTONS[target] = []
    ADD_BUTTONS[target].append({"text": btn_text, "url": url})
    save_add_buttons(ADD_BUTTONS)
    await state.clear()
    scope = "barcha kinolarga (global)" if target == "_global" else f"<code>{target}</code> kinosi uchun"
    await message.answer(f"✅ Tugma qo'shildi {scope}!\n\n{btn_text} — {url}", reply_markup=get_admin_extra_keyboard())

@dp.callback_query(F.data.startswith("editbtn"))
async def editbtn_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    parts = callback_query.data.split("|")
    if len(parts) != 3:
        await callback_query.answer("❌ Xatolik.", show_alert=True)
        return
    _, target, idx_str = parts
    try:
        idx = int(idx_str)
    except ValueError:
        await callback_query.answer("❌ Xatolik.", show_alert=True)
        return
    if target not in ADD_BUTTONS or idx >= len(ADD_BUTTONS[target]):
        await callback_query.answer("❌ Tugma topilmadi.", show_alert=True)
        return
    btn = ADD_BUTTONS[target][idx]
    await state.update_data(edit_target=target, edit_idx=idx, old_text=btn['text'], old_url=btn['url'])
    await state.set_state(AdminStates.edit_btn_text)
    await callback_query.message.answer(
        f"✏️ <b>Tugmani tahrirlash</b>\n\nHozirgi matn: <b>{btn['text']}</b>\nHozirgi havola: {btn['url']}\n\nYangi matn kiriting:\n<i>(O'zgartirmaslik uchun <code>.</code> yuboring)</i>",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]], resize_keyboard=True, one_time_keyboard=False)
    )
    await callback_query.answer()

@dp.message(AdminStates.edit_btn_text, F.text)
async def edit_btn_text_received(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_extra_keyboard())
        return
    data = await state.get_data()
    new_text = data['old_text'] if message.text.strip() == "." else message.text.strip()
    await state.update_data(new_text=new_text)
    await state.set_state(AdminStates.edit_btn_url)
    await message.answer(f"🔗 Yangi havola kiriting (o'zgartirmaslik uchun <code>.</code> yuboring):\n\nHozirgi: {data['old_url']}")

@dp.message(AdminStates.edit_btn_url, F.text)
async def edit_btn_url_received(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_extra_keyboard())
        return
    data = await state.get_data()
    new_url = data['old_url'] if message.text.strip() == "." else message.text.strip()
    if new_url != data['old_url'] and not new_url.startswith('http'):
        await message.answer("❌ Havola http:// yoki https:// bilan boshlanishi kerak.")
        return
    target = data['edit_target']
    idx = data['edit_idx']
    new_text = data['new_text']
    ADD_BUTTONS[target][idx] = {"text": new_text, "url": new_url}
    save_add_buttons(ADD_BUTTONS)
    await state.clear()
    await message.answer(f"✅ Tugma yangilandi!\n\nMatn: {new_text}\nHavola: {new_url}", reply_markup=get_admin_extra_keyboard())

@dp.callback_query(F.data.startswith("delbtn"))
async def delete_btn_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    parts = callback_query.data.split("|")
    if len(parts) != 3:
        await callback_query.answer("❌ Xatolik.", show_alert=True)
        return
    _, target, idx_str = parts
    try:
        idx = int(idx_str)
    except ValueError:
        await callback_query.answer("❌ Xatolik.", show_alert=True)
        return
    if target in ADD_BUTTONS and idx < len(ADD_BUTTONS[target]):
        removed = ADD_BUTTONS[target].pop(idx)
        save_add_buttons(ADD_BUTTONS)
        await callback_query.answer(f"✅ '{removed['text']}' o'chirildi.", show_alert=True)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=get_add_buttons_list_keyboard())
        except:
            pass
    else:
        await callback_query.answer("❌ Topilmadi.", show_alert=True)

@dp.message(F.text == "⭐ Top kinolar")
@dp.message(Command('top'))
async def top_movies_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📊 <b>Top kinolar</b>\n\nVaqt oralig'ini tanlang:", reply_markup=get_top_movies_keyboard())

@dp.callback_query(F.data.startswith("top_"))
async def top_movies_callback(callback_query: types.CallbackQuery):
    period = callback_query.data.replace("top_", "")
    names = {'day': "1 kunlik", 'week': "1 haftalik", 'month': "1 oylik",
             '6month': "6 oylik", 'year': "1 yillik", 'all': "Barcha vaqt", 'stats': "Statistika"}
    if period == 'stats':
        stats = get_total_stats()
        text = (f"📈 <b>Umumiy statistika:</b>\n\n"
                f"👁️ Bugun: {stats.get('today_views',0)}\n"
                f"📅 Hafta: {stats.get('week_views',0)}\n"
                f"📊 Oy: {stats.get('month_views',0)}\n"
                f"🔢 Jami: {stats.get('total_views',0)}\n")
        if stats.get('top_movie'):
            code, name, views = stats['top_movie']
            text += f"\n🏆 Eng ko'p: {name} ({code}) - {views} ta"
        await callback_query.message.edit_text(text, reply_markup=get_top_movies_keyboard())
    else:
        movies = get_top_movies_by_time(period)
        if movies:
            lines = [f"{i}. {name} (<code>{code}</code>) - {views} ta"
                     for i, (code, name, views) in enumerate(movies[:10], 1)]
            text = f"🏆 <b>{names[period].upper()} TOP 10:</b>\n\n" + "\n".join(lines)
        else:
            text = f"ℹ️ {names[period]} davrda statistika yo'q."
        await callback_query.message.edit_text(text, reply_markup=get_top_movies_keyboard())
    await callback_query.answer()

@dp.message(F.text == "📈 Kanal statistikasi")
async def channel_stats_button(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not CHANNELS and not PRIVATE_CHANNELS:
        await message.answer("ℹ️ Kanal qo'shilmagan.")
        return
    await message.answer("📈 <b>Kanal statistikasi</b>\n\nVaqt oralig'ini tanlang:", reply_markup=get_channel_stats_keyboard())

@dp.callback_query(F.data.startswith("chstat_"))
async def channel_stats_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    period = callback_query.data.replace("chstat_", "")
    period_names = {'today': 'Bugun', 'week': 'Hafta', 'month': 'Oy', 'year': 'Yil', 'all': 'Hammasi'}
    text = f"📈 <b>Kanal statistikasi ({period_names.get(period)}):</b>\n\n"
    all_channels = [(ch, "🔓") for ch in CHANNELS] + [(ch, "🔒") for ch in PRIVATE_CHANNELS]
    for ch, icon in all_channels:
        ch_full = ch if ch.startswith('@') else '@' + ch
        try:
            live = await bot.get_chat_member_count(ch_full)
        except:
            live = "N/A"
        db_count = get_channel_subscriber_stats(ch_full, period)
        text += f"{icon} <b>{ch}</b>\n├─ 👥 A'zolar: {live}\n└─ 🤖 Bot orqali: {db_count}\n\n"
    await callback_query.message.edit_text(text, reply_markup=get_channel_stats_keyboard())
    await callback_query.answer()

@dp.message(F.text == "🔍 Obuna test")
@dp.message(Command('test'))
async def test_subscription(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    results = []
    all_channels = list(CHANNELS) + list(PRIVATE_CHANNELS)
    for channel in all_channels:
        ch = channel if channel.startswith('@') else '@' + channel
        icon = "🔒" if channel in PRIVATE_CHANNELS else "🔓"
        try:
            member = await bot.get_chat_member(ch, message.from_user.id)
            results.append(f"✅ {icon} {ch}: {member.status}")
        except Exception as e:
            err = str(e).lower()
            if 'chat not found' in err:
                results.append(f"❌ {icon} {ch}: Kanal topilmadi")
            elif 'bot is not a member' in err or 'not enough rights' in err:
                results.append(f"⚠️ {icon} {ch}: Bot admin emas!")
            elif 'user not found' in err or 'participant' in err:
                results.append(f"⚠️ {icon} {ch}: Siz a'zo emassiz")
            else:
                results.append(f"❓ {icon} {ch}: {str(e)[:60]}")
    for bs in BOT_SUBSCRIPTIONS:
        uname = bs.get("username", "")
        in_db = check_bot_sub_in_db(message.from_user.id, uname)
        db_status = "DB da bor" if in_db else "DB da yoq"
        db_icon = "✅" if in_db else "❌"
        results.append(f"{db_icon} 🤖 {uname}: {db_status}")
    not_sub = await get_not_subscribed_channels(message.from_user.id)
    sub_status = "✅ Barcha shartlar bajarilgan" if not not_sub else f"❌ Bajarilmagan: {len(not_sub)} ta"
    await message.answer(f"🔧 <b>Obuna tekshiruv natijasi:</b>\n\n" + "\n".join(results) + f"\n\n👤 <b>Siz uchun:</b> {sub_status}")

class BlockStates(StatesGroup):
    waiting_block_id = State()
    waiting_unblock_id = State()

@dp.message(F.text == "🚫 User bloklash")
async def block_user_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(BlockStates.waiting_block_id)
    await message.answer("🚫 <b>User bloklash</b>\n\nBloklash uchun user ID yuboring:\n<i>Masalan: 123456789</i>", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]], resize_keyboard=True))

@dp.message(BlockStates.waiting_block_id, F.text)
async def block_user_process(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor.", reply_markup=get_admin_extra_keyboard())
        return
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ To'g'ri ID kiriting (faqat raqam).")
        return
    await state.clear()
    mark_user_blocked_bot(target_id)
    try:
        await bot.send_message(target_id, "🚫 Siz botdan bloklandingiz.")
    except:
        pass
    await message.answer(f"✅ <b>User bloklandi!</b>\n🆔 <code>{target_id}</code>", reply_markup=get_admin_extra_keyboard())

@dp.message(F.text == "✅ Blokdan chiqarish")
async def unblock_user_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(BlockStates.waiting_unblock_id)
    await message.answer("✅ <b>Blokdan chiqarish</b>\n\nUser ID yuboring:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]], resize_keyboard=True))

@dp.message(BlockStates.waiting_unblock_id, F.text)
async def unblock_user_process(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor.", reply_markup=get_admin_extra_keyboard())
        return
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ To'g'ri ID kiriting.")
        return
    await state.clear()
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_blocked_bot=FALSE WHERE user_id=%s", (target_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        await message.answer(f"❌ Xato: {e}", reply_markup=get_admin_extra_keyboard())
        return
    try:
        await bot.send_message(target_id, "✅ Siz botdan blokdan chiqarildingiz!")
    except:
        pass
    await message.answer(f"✅ <b>Blokdan chiqarildi!</b>\n🆔 <code>{target_id}</code>", reply_markup=get_admin_extra_keyboard())

@dp.message(F.text == "📬 Buyurtmalar")
async def admin_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    orders = get_pending_orders()
    if not orders:
        await message.answer("📬 Kutilayotgan buyurtma yo'q.")
        return
    for order in orders[:10]:
        oid, uid, username, first_name, order_text, ordered_date = order
        uname = f"@{username}" if username else (first_name or str(uid))
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="↩️ Javob", callback_data=f"reply_{uid}"),
            InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"order_done_{oid}")
        ]])
        await message.answer(f"📬 <b>Buyurtma #{oid}</b>\n\n👤 {uname} (<code>{uid}</code>)\n📝 {order_text}\n🕐 {ordered_date.strftime('%d.%m.%Y %H:%M')}", reply_markup=kb)

@dp.callback_query(F.data.startswith("order_done_"))
async def order_done_cb(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    order_id = int(callback_query.data.replace("order_done_", ""))
    mark_order_done(order_id)
    await callback_query.answer(f"✅ Buyurtma #{order_id} bajarildi.", show_alert=True)
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except:
        pass

@dp.message(F.text == "💬 Xabarlar")
async def admin_messages(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, username, first_name, message_text, is_answered, sent_date FROM contact_messages ORDER BY sent_date DESC LIMIT 10")
        msgs = c.fetchall()
        conn.close()
    except:
        msgs = []
    if not msgs:
        await message.answer("💬 Hozircha xabar yo'q.")
        return
    for msg in msgs:
        mid, uid, username, first, text, answered, sent_date = msg
        uname = f"@{username}" if username else (first or str(uid))
        status = "✅ Javob berilgan" if answered else "⏳ Kutilmoqda"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"reply_{uid}")]]) if not answered else None
        await message.answer(f"💬 <b>#{mid}</b> | {uname} (<code>{uid}</code>)\n📝 {text or '[media]'}\n🕐 {sent_date.strftime('%d.%m.%Y %H:%M')}\n{status}", reply_markup=kb)

# ==================== QISM CALLBACK ====================
@dp.callback_query(F.data.startswith("part_"))
async def part_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data_parts = callback_query.data.split("_")
    code = data_parts[1]
    part_number = int(data_parts[2])
    part = get_movie_part(code, part_number)
    if part:
        file_id, part_name = part
        increment_part_view(code, part_number, user_id)
        success = await send_part_to_user(user_id, file_id, part_name, code, part_number, user_id)
        if success:
            await callback_query.answer("✅ Kino yuborildi!")
        else:
            await callback_query.answer("❌ Xatolik yuz berdi!", show_alert=True)
    else:
        await callback_query.answer("❌ Qism topilmadi!", show_alert=True)

# ==================== KO'P QISMLI ADMIN ====================
@dp.message(AdminStates.waiting_part_code, F.text)
async def add_part_code(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return
    code = message.text.strip().upper()
    await state.update_data(part_code=code)
    parts = get_movie_parts(code)
    next_part = len(parts) + 1
    await state.update_data(part_number=next_part)
    if parts:
        await state.set_state(AdminStates.waiting_part_video)
        parts_info = "\n".join([f"  {p[0]}-qism" for p in parts])
        await message.answer(f"📺 Serial: <code>{code}</code>\nMavjud qismlar:\n{parts_info}\n\n📤 {next_part}-qism videosini yuboring:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]], resize_keyboard=True))
    else:
        await state.set_state(AdminStates.waiting_part_name)
        await message.answer(f"✅ Kod: <code>{code}</code>\n\n📝 Serial nomini kiriting:\n<i>Masalan: Avatar, Squid Game</i>", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]], resize_keyboard=True))

@dp.message(AdminStates.waiting_part_name, F.text)
async def serial_name_received(message: types.Message, state: FSMContext):
    if message.text.strip() in ["❌ Bekor", "❌ bekor"]:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return
    serial_name = " ".join(message.text.strip().split())
    await state.update_data(serial_name=serial_name)
    await state.set_state(AdminStates.waiting_part_video)
    data = await state.get_data()
    await message.answer(f"✅ Serial: <b>{serial_name}</b> (<code>{data['part_code']}</code>)\n\n📤 1-qism videosini yuboring:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor")]], resize_keyboard=True))

@dp.message(AdminStates.waiting_part_video, F.video)
async def add_part_video(message: types.Message, state: FSMContext):
    await state.update_data(part_file_id=message.video.file_id)
    data = await state.get_data()
    part_number = data['part_number']
    part_code = data['part_code']
    serial_name = data.get('serial_name', part_code)
    part_name = f"{part_number}-qism"
    result = add_movie_part(part_code, part_number, data['part_file_id'], part_name, message.from_user.id)
    if result:
        parts = get_movie_parts(part_code)
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Keyingi qismni qo'shish", callback_data=f"addmore_{part_code}")],
            [InlineKeyboardButton(text="✅ Tugatish", callback_data="addpart_done")]
        ])
        await message.answer(f"✅ <b>{serial_name}</b> — {part_number}-qism qo'shildi!\n\n🔢 Kod: <code>{part_code}</code>\n📊 Jami qismlar: {len(parts)} ta\n\nDavom etasizmi?", reply_markup=builder)
    else:
        await message.answer("❌ Xatolik yuz berdi!")
    await state.clear()

@dp.callback_query(F.data.startswith("addmore_"))
async def add_more_part(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    code = callback_query.data.replace("addmore_", "")
    parts = get_movie_parts(code)
    next_part = len(parts) + 1
    serial_name = code
    await state.update_data(part_code=code, part_number=next_part, serial_name=serial_name)
    await state.set_state(AdminStates.waiting_part_video)
    try:
        await callback_query.message.edit_text(f"📤 <b>{serial_name}</b> — {next_part}-qism videosini yuboring:")
    except:
        await callback_query.message.answer(f"📤 {next_part}-qism videosini yuboring:")
    await callback_query.answer()

@dp.callback_query(F.data == "addpart_done")
async def add_part_done(callback_query: types.CallbackQuery):
    try:
        await callback_query.message.edit_text("✅ Kino qismlari saqlandi!")
    except:
        pass
    await callback_query.answer()

# ==================== ASOSIY HANDLER ====================
ADMIN_KEYBOARD_BUTTONS = [
    "🎬 Kino qo'shish", "📋 Kinolar ro'yxati", "🗑️ Kino o'chirish",
    "⚠️ Hammasini o'chir", "📊 Statistika", "👥 Foydalanuvchilar",
    "📢 Reklama yuborish", "📡 Kanallar ro'yxati", "🔧 Qo'shimcha buyruqlar",
    "📋 Reklamalar ro'yxati", "❌ Reklamani o'chirish", "🔍 Obuna test",
    "⭐ Top kinolar", "📈 Kanal statistikasi", "➕ Kanal qo'shish",
    "➖ Kanal o'chirish", "🔒 Yopiq kanal qo'shish", "🤖 Bot obunalari",
    "🔗 Add buttons boshqaruv", "📬 Buyurtmalar", "💬 Xabarlar", "🏠 Asosiy panel",
    "❌ Bekor", "⭐ Sevimlilar", "📞 Aloqa"
]

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_all_messages(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = message.from_user
    current_state = await state.get_state()

    if user_id == ADMIN_ID:
        if message.text in ADMIN_KEYBOARD_BUTTONS and current_state is not None:
            await state.clear()
        return

    user_reply_btns = ["⭐ Sevimlilar", "📞 Aloqa"]
    if message.text in user_reply_btns and current_state is not None:
        await state.clear()

    if current_state is not None:
        return
    add_user_to_db(user_id, user.username, user.first_name, user.last_name, False)
    lang = get_user_language(user_id)
    if lang is None:
        await message.answer(TEXTS["uz"]["welcome"], reply_markup=get_language_keyboard())
        return
    movie_code = message.text.strip().upper()
    parts = get_movie_parts(movie_code)
    result = get_movie_from_db(movie_code)

    if parts or result:
        if not await is_subscribed(user_id):
            not_sub = await get_not_subscribed_channels(user_id)
            await message.answer(TEXTS[lang]['not_subscribed_msg'], reply_markup=get_subscribe_keyboard_v2(lang, not_sub))
            return

    if parts:
        parts_text = f"🎬 <b>{movie_code}</b> — qismlar ({len(parts)} ta)\n\n"
        for pnum, _, pname, _ in parts:
            parts_text += f"  {pnum}. {pname}\n"
        parts_text += "\n👇 Qismni tanlang:"
        await message.answer(parts_text, reply_markup=get_parts_keyboard(movie_code, parts, lang))
        return

    if result:
        file_id, movie_name = result
        try:
            wait_msg = await message.answer(TEXTS[lang]['loading'])
            success = await send_movie_to_user(message.chat.id, file_id, movie_name, movie_code, user_id, lang)
            if success:
                try:
                    await wait_msg.delete()
                except:
                    pass
            else:
                await wait_msg.edit_text(TEXTS[lang]['error'])
        except Exception as e:
            print(f"❌ Error: {e}")
            await message.answer(TEXTS[lang]['error'])
    else:
        if re.match(r'^[A-Z0-9]{2,15}$', movie_code):
            await message.answer(TEXTS[lang]['movie_not_found'])

# ==================== MAIN ====================
async def main():
    await set_bot_description()
    init_db()
    print(f"✅ Bot ishga tushdi! Admin: {ADMIN_ID}")
    print(f"📡 Ochiq kanallar: {CHANNELS}")
    print(f"🔒 Yopiq kanallar: {PRIVATE_CHANNELS}")
    print(f"🤖 Bot obunalari: {[b.get('username') for b in BOT_SUBSCRIPTIONS]}")
    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query", "chat_join_request"],
        drop_pending_updates=True
    )

if __name__ == '__main__':
    asyncio.run(main())