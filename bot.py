import asyncio
import os
import uuid
import subprocess

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================== KEYBOARDS ==================

def start_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬇️ Как скачать", callback_data="help_download")],
            [InlineKeyboardButton(text="ℹ️ О боте", callback_data="help_about")],
        ]
    )

def after_download_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬇️ Скачать ещё", callback_data="again")],
        ]
    )

# ================== START ==================

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "👋 *Video Downloader Bot*\n\n"
        "Поддержка:\n"
        "• TikTok\n"
        "• YouTube Shorts\n"
        "• Instagram Reels\n\n"
        "Просто пришли ссылку 👇",
        parse_mode="Markdown",
        reply_markup=start_kb()
    )

# ================== AGAIN ==================

@dp.callback_query(lambda c: c.data == "again")
async def again_cb(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass
    await bot.send_message(callback.from_user.id, "🔗 Пришли новую ссылку:")
    await callback.answer()

# ================== MAIN ==================

@dp.message()
async def handle_link(msg: types.Message):
    if not msg.text:
        return

    url = msg.text.strip()
    if not url.startswith("http"):
        await msg.answer("❌ Это не ссылка")
        return

    status = await msg.answer("⏳ Скачиваю ...")

    uid = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

    cmd = [
        "python", "-m", "yt_dlp",
        "-f", "bestvideo*+bestaudio/best",
        "--merge-output-format", "mp4",
        "--recode-video", "mp4",
        "--postprocessor-args", "ffmpeg:-c:v copy -c:a aac",
        "--no-playlist",
        "-o", output_template,
        url
    ]

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if process.returncode != 0:
            print(process.stdout)
            print(process.stderr)
            await status.edit_text("❌ Ошибка скачивания.")
            return
    except Exception as e:
        print("ERROR:", e)
        await status.edit_text("❌ Ошибка скачивания.")
        return

    # ================= FIND FILE =================

    final_file = None
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(uid) and f.endswith(".mp4"):
            final_file = os.path.join(DOWNLOAD_DIR, f)
            break

    if not final_file:
        await status.edit_text("❌ Файл не найден.")
        return

    # ================= SEND =================

    await status.edit_text("📤 Отправляю...")

    await msg.answer_video(
        types.FSInputFile(final_file),
        caption="✅ Готово !",
        supports_streaming=True
    )

    await msg.answer("⬇️ Хочешь ещё ?", reply_markup=after_download_kb())

    try:
        await status.delete()
    except:
        pass

    try:
        os.remove(final_file)
    except:
        pass

# ================== RUN ==================

async def main():
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
