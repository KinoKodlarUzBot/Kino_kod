import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# 🛠 MA'LUMOTLARINGIZ JOY-JOYIGA QO'YILDI
TOKEN = "8654330963:AAHz1fjClGFiuMB4lmzTjQVofA9AXnb_cmw"
CHANNEL_ID = -1002323674089  # Yopiq kanal ID-si (Raqam formatida)
CHANNEL_LINK = "https://t.me/+fuM6hLyhJ6ZhNzEy"  # Yopiq kanal taklif havolasi

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 📦 KINOLAR BAZASI
# Bot ishga tushgach, unga video yuborsangiz, sizga yangi file_id beradi. 
# Ularni shu yerga qo'shib borasiz. Hozircha namuna sifatida "240" kodi turibdi.
films = {
    "240": {
        "file_id": "BAACAgIAAxkBAAMZ...namuna_id",  
        "caption": (
            "#🎬 Chegara qo'riqchilari\n\n"
            "🎭 Janr: #Jangari, #Sarguzasht\n"
            "🌍 Davlat: Ukraina\n"
            "📺 Sifat: 480p / HD\n"
            "🎙 Tarjima: O'zbekcha\n\n"
            "✨ *•────────•⭐•────────•* ✨\n"
            "Do'stlaringizga Jo'nating"
        )
    }
}

# --- Obunani tekshirish funksiyasi ---
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["left", "kicked"]:
            return False
        return True
    except Exception:
        # Agar bot kanalda admin bo'lmasa yoki xatolik yuz bersa
        return False

# --- /start buyrug'i ---
@dp.message(CommandStart())
async def start_cmd(msg: types.Message):
    first_name = msg.from_user.first_name
    await msg.answer(
        f"👋 Assalomu alaykum {first_name} botimizga xush kelibsiz.\n\n"
        f"✍ *Kino kodini yuboring.*", 
        parse_mode="Markdown"
    )

# --- ADMIN UCHUN: file_id aniqlash ---
# Botga video yuborsangiz, sizga uning file_id sini qaytaradi
@dp.message(lambda message: message.video)
async def get_video_id(msg: types.Message):
    await msg.answer(f"📹 Kinoning `file_id` kodi:\n\n`{msg.video.file_id}`", parse_mode="Markdown")

# --- Kinoni tekshirish va yuborish mantiqi ---
async def send_movie_or_ask_sub(msg: types.Message, code: str, is_callback=False):
    user_id = msg.from_user.id if is_callback else msg.chat.id
    
    # 1. Obunani tekshiramiz
    is_subscribed = await check_subscription(msg.from_user.id)
    
    if not is_subscribed:
        # Obuna bo'lmagan bo'lsa, skrinshotdagi kabi majburiy havola oynasi chiqadi
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 - kanal ↗️", url=CHANNEL_LINK)],
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"check_{code}")]
        ])
        
        text = "❌ Kechirasiz botimizdan foydalanishdan oldin ushbu kanallarga a'zo bo'lishingiz kerak."
        if is_callback:
            await msg.answer(text, reply_markup=kb)
        else:
            await msg.reply(text, reply_markup=kb)
        return

    # 2. Obuna bo'lsa, kinoni yuboramiz
    if code in films:
        movie = films[code]
        bot_username = (await bot.get_me()).username
        
        # Do'stlarga ulashish havolasi (Kino kodi bilan birga)
        share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start={code}&text=Kino%20kod:%20{code}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="♻️ Do'stlarga ulashish", url=share_url)],
            [InlineKeyboardButton(text="❌", callback_data="delete_msg")]
        ])
        
        if is_callback:
            await msg.delete() # Obuna ogohlantirishini o'chirish
            
        await bot.send_chat_action(chat_id=user_id, action="upload_video")
        await bot.send_video(chat_id=user_id, video=movie["file_id"], caption=movie["caption"], reply_markup=kb)
    else:
        await bot.send_message(chat_id=user_id, text="❌ Kechirasiz, bunday kodli kino topilmadi.")

# --- Matnli xabar kelganda (Kod terilganda) ---
@dp.message()
async def text_handler(msg: types.Message):
    await send_movie_or_ask_sub(msg, msg.text.strip())

# --- "Tasdiqlash" tugmasi bosilganda ---
@dp.callback_query(lambda call: call.data.startswith("check_"))
async def check_callback(call: types.CallbackQuery):
    code = call.data.split("_")[1]
    if await check_subscription(call.from_user.id):
        await send_movie_or_ask_sub(call.message, code, is_callback=True)
    else:
        await call.answer("🚫 Siz hali ham kanalga a'zo bo'lmadingiz!", show_alert=True)

# --- Xabarni o'chirish (❌ tugmasi) ---
@dp.callback_query(lambda call: call.data == "delete_msg")
async def delete_callback(call: types.CallbackQuery):
    await call.message.delete()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
