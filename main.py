import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ⚙️ ASOSIY SOZLAMALAR
TOKEN = "8654330963:AAHz1fjClGFiuMB4lmzTjQVofA9AXnb_cmw"
ADMIN_ID = 6905227976  # Shaxsiy Telegram ID raqamingiz

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 🗄 MA'LUMOTLAR BAZASINI SOZLASH
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()

# Sozlamalar jadvali
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

# Kinolar jadvali
cursor.execute("""
CREATE TABLE IF NOT EXISTS films (
    code TEXT PRIMARY KEY,
    file_id TEXT,
    caption TEXT
)
""")

# Foydalanuvchilarni hisoblash jadvali
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")
conn.commit()

# Boshlang'ich majburiy obuna sozlamalari
try:
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channels_id', '-1002323674089')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channels_link', 'https://t.me/+fuM6hLyhJ6ZhNzEy')")
    conn.commit()
except Exception:
    pass

# ✨ YANGILANDI: Yangi holatlar qo'shildi
class AdminStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_code = State()
    waiting_for_caption = State()
    waiting_for_channels_id = State()
    waiting_for_channels_link = State()
    waiting_for_del_code = State()  # O'chirish uchun
    waiting_for_reklama = State()   # Reklama uchun

def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else None

def set_setting(key, value):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

def add_user(user_id):
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
    except Exception:
        pass

# 🔥 YANGILANDI: Trafik daxshatli ko'p bo'lganda ham qotmaydigan tizim
async def check_all_subscriptions(user_id: int) -> bool:
    ids_str = get_setting("channels_id")
    if not ids_str:
        return True
    
    channel_ids = [id.strip() for id in ids_str.split(",") if id.strip()]
    
    for ch_id in channel_ids:
        try:
            member = await bot.get_chat_member(chat_id=int(ch_id), user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            # Agar Telegram ko'p so'rov uchun vaqtincha bloklasa (FloodWait), bot qotmasligi uchun o'tkazib yuboradi
            if "retry after" in str(e).lower():
                return True
            continue
    return True

@dp.message(CommandStart())
async def start_cmd(msg: types.Message):
    add_user(msg.from_user.id)
    
    args = msg.text.split()
    if len(args) > 1:
        code = args[1].strip()
        await send_movie_or_ask_sub(msg, code)
        return

    is_subscribed = await check_all_subscriptions(msg.from_user.id)
    if not is_subscribed:
        links_str = get_setting("channels_link")
        links = [l.strip() for l in links_str.split(",") if l.strip()]
        
        inline_keyboard = []
        for index, link in enumerate(links, start=1):
            inline_keyboard.append([InlineKeyboardButton(text=f"{index} - kanal ↗️", url=link)])
        
        inline_keyboard.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_none")])
        kb = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        
        await msg.answer("❌ Kechirasiz botimizdan foydalanishdan oldin ushbu kanallarga a'zo bo'lishingiz kerak.", reply_markup=kb)
        return

    await msg.answer(
        f"👋 Assalomu alaykum {msg.from_user.first_name} botimizga xush kelibsiz.\n\n"
        f"✍ *Kino kodini yuboring.*", 
        parse_mode="Markdown"
    )

@dp.message(Command("stat"))
async def show_statistics(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM films")
    total_films = cursor.fetchone()[0]
    
    text = (
        f"📊 **Bot statistikasi:**\n\n"
        f"👤 **Jami foydalanuvchilar:** {total_users} ta\n"
        f"🎬 **Jami yuklangan kinolar:** {total_films} ta"
    )
    await msg.answer(text, parse_mode="Markdown")

# 🔥 YANGILANDI: Admin panelga yangi tugmalar qo'shildi
@dp.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="admin_add_kino"),
         InlineKeyboardButton(text="❌ Kinoni o'chirish", callback_data="admin_del_kino")],
        [InlineKeyboardButton(text="📢 Kanallar ID sini o'zgartirish", callback_data="admin_set_id")],
        [InlineKeyboardButton(text="🔗 Kanallar havolalarini o'zgartirish", callback_data="admin_set_link")],
        [InlineKeyboardButton(text="📢 Reklama tarqatish", callback_data="admin_send_reklama")],
        [InlineKeyboardButton(text="📊 Hozirgi sozlamalar", callback_data="admin_view_settings")]
    ])
    await msg.answer("⚙️ *Bot boshqaruv paneli:*", reply_markup=kb, parse_mode="Markdown")

# 🔥 YANGILANDI: Yangi callback funksiyalar qo'shildi
@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    
    action = call.data
    await call.answer()
    
    if action == "admin_view_settings":
        ch_ids = get_setting("channels_id")
        ch_links = get_setting("channels_link")
        cursor.execute("SELECT COUNT(*) FROM films")
        total_films = cursor.fetchone()[0]
        
        text = f"📊 *Hozirgi sozlamalar:*\n\n📢 Kanallar ID: `{ch_ids}`\n🔗 Kanallar Linklari: {ch_links}\n🎬 Jami kinolar: {total_films} ta"
        await call.message.answer(text, parse_mode="Markdown")
        
    elif action == "admin_add_kino":
        await call.message.answer("📹 Menga kino videosini yuboring:")
        await state.set_state(AdminStates.waiting_for_video)
        
    elif action == "admin_del_kino":
        await call.message.answer("❌ O'chirmoqchi bo'lgan kino *KODINI* yuboring:", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_del_code)
        
    elif action == "admin_send_reklama":
        await call.message.answer("📢 Barcha obunachilarga yuboriladigan reklamani yuboring (Matn, rasm yoki video):")
        await state.set_state(AdminStates.waiting_for_reklama)
        
    elif action == "admin_set_id":
        await call.message.answer("✍ Yangi kanallar ID larini **vergul** bilan ajratib yuboring:\n\n*Masalan:* `-100123,-100456`", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_channels_id)
        
    elif action == "admin_set_link":
        await call.message.answer("✍ Yangi kanallar linklarini **vergul** bilan ajratib yuboring:\n\n*Masalan:* `https://t.me/link1,https://t.me/link2`", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_channels_link)

@dp.message(AdminStates.waiting_for_video, F.video)
async def process_video(msg: types.Message, state: FSMContext):
    await state.update_data(file_id=msg.video.file_id)
    await msg.answer("🔢 Endi ushbu kino uchun *KOD* yuboring:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_code)

@dp.message(AdminStates.waiting_for_code)
async def process_code(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text.strip())
    await msg.answer("📝 Endi kinoning *TAVSIFI (Caption)* matnini yuboring:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_caption)

@dp.message(AdminStates.waiting_for_caption)
async def process_caption(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data['code']
    file_id = data['file_id']
    caption = msg.text
    
    cursor.execute("INSERT OR REPLACE INTO films (code, file_id, caption) VALUES (?, ?, ?)", (code, file_id, caption))
    conn.commit()
    
    await msg.answer(f"✅ *Kino muvaffaqiyatli saqlandi!*\n🔑 Kodi: `{code}`", parse_mode="Markdown")
    await state.clear()

# 🔥 YANGI: Kinoni o'chirish jarayoni
@dp.message(AdminStates.waiting_for_del_code)
async def process_delete_movie(msg: types.Message, state: FSMContext):
    code = msg.text.strip()
    cursor.execute("SELECT code FROM films WHERE code=?", (code,))
    if cursor.fetchone():
        cursor.execute("DELETE FROM films WHERE code=?", (code,))
        conn.commit()
        await msg.answer(f"❌ `{code}` kodli kino bazadan muvaffaqiyatli o'chirildi!", parse_mode="Markdown")
    else:
        await msg.answer(f"⚠️ Bazada `{code}` kodli kino topilmadi!", parse_mode="Markdown")
    await state.clear()

# 🔥 YANGI: Reklama tarqatish (Mailing) jarayoni
@dp.message(AdminStates.waiting_for_reklama)
async def process_send_reklama(msg: types.Message, state: FSMContext):
    await msg.answer("🚀 Reklama daxshatli tezlikda yuborilmoqda, kuting...")
    await state.clear()
    
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    
    success, failed = 0, 0
    for u in users:
        try:
            await msg.copy_to(chat_id=u[0])
            success += 1
            await asyncio.sleep(0.05)  # Blok tushmasligi uchun o'ta muhim pauza
        except Exception:
            failed += 1
            
    await msg.answer(f"📊 **Reklama yakunlandi:**\n\n✅ Yetkazildi: {success} ta\n❌ Yetkazilmadi: {failed} ta")

@dp.message(AdminStates.waiting_for_channels_id)
async def process_ch_ids(msg: types.Message, state: FSMContext):
    set_setting("channels_id", msg.text.strip())
    await msg.answer("✅ Kanallar ID-lari bazada yangilandi!")
    await state.clear()

@dp.message(AdminStates.waiting_for_channels_link)
async def process_ch_links(msg: types.Message, state: FSMContext):
    set_setting("channels_link", msg.text.strip())
    await msg.answer("✅ Kanallar havolalari bazada yangilandi!")
    await state.clear()

async def send_movie_or_ask_sub(msg: types.Message, code: str, is_callback=False):
    user_id = msg.from_user.id if is_callback else msg.chat.id
    add_user(msg.from_user.id)
    
    is_subscribed = await check_all_subscriptions(msg.from_user.id)
    links_str = get_setting("channels_link")
    
    if not is_subscribed:
        links = [l.strip() for l in links_str.split(",") if l.strip()]
        
        inline_keyboard = []
        for index, link in enumerate(links, start=1):
            inline_keyboard.append([InlineKeyboardButton(text=f"{index} - kanal ↗️", url=link)])
        
        inline_keyboard.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"check_{code}")])
        kb = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        
        text = "❌ Kechirasiz botimizdan foydalanishdan oldin ushbu kanallarga a'zo bo'lishingiz kerak."
        if is_callback:
            try: await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)
            except: pass
        else:
            await msg.reply(text, reply_markup=kb)
        return

    cursor.execute("SELECT file_id, caption FROM films WHERE code=?", (code,))
    res = cursor.fetchone()
    
    if res:
        file_id, caption = res[0], res[1]
        bot_username = (await bot.get_me()).username
        share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start={code}&text=Kino%20kod:%20{code}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="♻️ Do'stlarga ulashish", url=share_url)],
            [InlineKeyboardButton(text="❌", callback_data="delete_msg")]
        ])
        
        if is_callback:
            try: await msg.delete()
            except: pass
            
        await bot.send_chat_action(chat_id=user_id, action="upload_video")
        await bot.send_video(chat_id=user_id, video=file_id, caption=caption, reply_markup=kb)
    else:
        await bot.send_message(chat_id=user_id, text="❌ Kechirasiz, bunday kodli kino topilmadi.")

@dp.message()
async def text_handler(msg: types.Message):
    await send_movie_or_ask_sub(msg, msg.text.strip())

@dp.callback_query(F.data.startswith("check_"))
async def check_callback(call: types.CallbackQuery):
    code = call.data.split("_")[1]
    await call.answer()  # Qotib qolishni oldini oladi
    
    if await check_all_subscriptions(call.from_user.id):
        if code == "none" or not code:
            try: await call.message.delete()
            except: pass
            await call.message.answer("✅ **Tabriklayman, obuna tasdiqlandi!**\n\n🎬 Endi o'zingiz ko'rmoqchi bo'lgan kino kodini yuboring:", parse_mode="Markdown")
        else:
            await send_movie_or_ask_sub(call.message, code, is_callback=True)
    else:
        await call.answer("🚫 Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

@dp.callback_query(F.data == "delete_msg")
async def delete_callback(call: types.CallbackQuery):
    await call.message.delete()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
