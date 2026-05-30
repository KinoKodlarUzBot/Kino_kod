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
ADMIN_ID = 6363577395  # 👈 AGAR TELEGRAM ID-INGIZ O'ZGARGANDAN BO'LSA, TO'G'RILAB QO'YING!

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 🗄 MA'LUMOTLAR BAZASINI SOZLASH (SQLite)
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()

# Jadvallarni yaratish (Sozlamalar va Kinolar uchun)
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS films (
    code TEXT PRIMARY KEY,
    file_id TEXT,
    caption TEXT
)
""")
conn.commit()

# Standart sozlamalarni boshlang'ich kiritish (Agar baza bo'sh bo'lsa)
try:
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_id', '-1002323674089')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_link', 'https://t.me/+fuM6hLyhJ6ZhNzEy')")
    conn.commit()
except Exception:
    pass

# 🎭 FSM (Admin ketma-ketlik shtatlari)
class AdminStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_code = State()
    waiting_for_caption = State()
    waiting_for_channel_id = State()
    waiting_for_channel_link = State()

# --- Dinamik funksiyalar (Bazadan o'qish va yozish) ---
def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else None

def set_setting(key, value):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

async def check_subscription(user_id: int) -> bool:
    try:
        ch_id = int(get_setting("channel_id"))
        member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
        if member.status in ["left", "kicked"]:
            return False
        return True
    except Exception:
        # Bot kanalda admin bo'lmasa yoki xato link bo'lsa tekshiruvdan o'tkazmaydi
        return False

# --- /start buyrug'i ---
@dp.message(CommandStart())
async def start_cmd(msg: types.Message):
    # Agar havola orqali kod bilan kirilgan bo'lsa (t.me/bot?start=230)
    args = msg.text.split()
    if len(args) > 1:
        code = args[1].strip()
        await send_movie_or_ask_sub(msg, code)
        return

    first_name = msg.from_user.first_name
    await msg.answer(
        f"👋 Assalomu alaykum {first_name} botimizga xush kelibsiz.\n\n"
        f"✍ *Kino kodini yuboring.*", 
        parse_mode="Markdown"
    )

# --- /admin panel buyrug'i ---
@dp.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="admin_add_kino")],
        [InlineKeyboardButton(text="📢 Kanal ID sini o'zgartirish", callback_data="admin_set_id")],
        [InlineKeyboardButton(text="🔗 Kanal havolasini o'zgartirish", callback_data="admin_set_link")],
        [InlineKeyboardButton(text="📊 Hozirgi sozlamalar", callback_data="admin_view_settings")]
    ])
    await msg.answer("⚙️ *Bot boshqaruv paneli:*", reply_markup=kb, divide_buttons=True, parse_mode="Markdown")

# --- Admin panel tugmalari boshqaruvi ---
@dp.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    
    action = call.data
    
    if action == "admin_view_settings":
        ch_id = get_setting("channel_id")
        ch_link = get_setting("channel_link")
        cursor.execute("SELECT COUNT(*) FROM films")
        total_films = cursor.fetchone()[0]
        
        text = f"📊 *Hozirgi sozlamalar:*\n\n📢 Kanal ID: `{ch_id}`\n🔗 Kanal Linki: {ch_link}\n🎬 Jami kinolar: {total_films} ta"
        await call.message.answer(text, parse_mode="Markdown")
        await call.answer()
        
    elif action == "admin_add_kino":
        await call.message.answer("📹 Menga kino videosini yuboring:")
        await state.set_state(AdminStates.waiting_for_video)
        await call.answer()
        
    elif action == "admin_set_id":
        await call.message.answer("✍ Yangi kanal ID sini yuboring (Masalan: -10012345678):")
        await state.set_state(AdminStates.waiting_for_channel_id)
        await call.answer()
        
    elif action == "admin_set_link":
        await call.message.answer("✍ Yangi kanal taklif havolasini (linkini) yuboring:")
        await state.set_state(AdminStates.waiting_for_channel_link)
        await call.answer()

# --- FSM jarayonlari (Admin tomonidan ma'lumot kiritilishi) ---
@dp.message(AdminStates.waiting_for_video, F.video)
async def process_video(msg: types.Message, state: FSMContext):
    await state.update_data(file_id=msg.video.file_id)
    await msg.answer("🔢 Endi ushbu kino uchun *KOD* yuboring (Masalan: 230):", parse_mode="Markdown")
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
    
    # Bazaga yozish (Agar o'sha kodli kino bo'lsa, ustidan yangilab yozadi)
    cursor.execute("INSERT OR REPLACE INTO films (code, file_id, caption) VALUES (?, ?, ?)", (code, file_id, caption))
    conn.commit()
    
    await msg.answer(f"✅ *Kino muvaffaqiyatli saqlandi!*\n🔑 Kodi: `{code}`", parse_mode="Markdown")
    await state.clear()

@dp.message(AdminStates.waiting_for_channel_id)
async def process_ch_id(msg: types.Message, state: FSMContext):
    set_setting("channel_id", msg.text.strip())
    await msg.answer("✅ Kanal ID-si bazada yangilandi!")
    await state.clear()

@dp.message(AdminStates.waiting_for_channel_link)
async def process_ch_link(msg: types.Message, state: FSMContext):
    set_setting("channel_link", msg.text.strip())
    await msg.answer("✅ Kanal havolasi bazada yangilandi!")
    await state.clear()

# --- Kinoni tekshirish va yuborish mantiqi ---
async def send_movie_or_ask_sub(msg: types.Message, code: str, is_callback=False):
    user_id = msg.from_user.id if is_callback else msg.chat.id
    
    # 1. Obunani tekshirish
    is_subscribed = await check_subscription(msg.from_user.id)
    ch_link = get_setting("channel_link")
    
    if not is_subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 - kanal ↗️", url=ch_link)],
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"check_{code}")]
        ])
        
        text = "❌ Kechirasiz botimizdan foydalanishdan oldin ushbu kanallarga a'zo bo'lishingiz kerak."
        if is_callback:
            try: await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)
            except: pass
        else:
            await msg.reply(text, reply_markup=kb)
        return

    # 2. Obuna bo'lsa, kinoni bazadan qidirish
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

# --- Matnli xabar kelganda (Oddiy odam kod yuborganda) ---
@dp.message()
async def text_handler(msg: types.Message):
    await send_movie_or_ask_sub(msg, msg.text.strip())

# --- "Tasdiqlash" tugmasi bosilganda ---
@dp.callback_query(F.data.startswith("check_"))
async def check_callback(call: types.CallbackQuery):
    code = call.data.split("_")[1]
    if await check_subscription(call.from_user.id):
        await send_movie_or_ask_sub(call.message, code, is_callback=True)
    else:
        await call.answer("🚫 Siz hali ham kanalga a'zo bo'lmadingiz!", show_alert=True)

# --- Xabarni o'chirish (❌ tugmasi) ---
@dp.callback_query(F.data == "delete_msg")
async def delete_callback(call: types.CallbackQuery):
    await call.message.delete()

# --- Botni ishga tushirish ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
