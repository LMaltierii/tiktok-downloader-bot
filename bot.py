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

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"

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
        "• Reels\n\n"
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

    status = await msg.answer("⏳ Скачиваю...")

    uid = str(uuid.uuid4())
    video_path = os.path.join(DOWNLOAD_DIR, f"{uid}_video.mp4")
    audio_path = os.path.join(DOWNLOAD_DIR, f"{uid}_audio.m4a")
    final_path = os.path.join(DOWNLOAD_DIR, f"{uid}.mp4")

    # 1️⃣ СКАЧИВАЕМ ВИДЕО
    cmd_video = [
        "python", "-m", "yt_dlp",
        "-f", "bv*",
        "-o", video_path,
        "--no-playlist",
        url
    ]

    # 2️⃣ СКАЧИВАЕМ АУДИО
    cmd_audio = [
        "python", "-m", "yt_dlp",
        "-f", "ba*",
        "-o", audio_path,
        "--no-playlist",
        url
    ]

    try:
        subprocess.run(cmd_video, check=True, timeout=300)
        subprocess.run(cmd_audio, check=True, timeout=300)
    except:
        await status.edit_text("❌ Ошибка скачивания потоков.")
        return

    # 3️⃣ СКЛЕИВАЕМ ЧЕРЕЗ FFMPEG
    merge_cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        final_path
    ]

    try:
        subprocess.run(merge_cmd, check=True, timeout=300)
    except:
        await status.edit_text("❌ Ошибка склейки ffmpeg.")
        return

    if not os.path.exists(final_path):
        await status.edit_text("❌ Финальный файл не создан.")
        return

    # 4️⃣ ОТПРАВЛЯЕМ
    await status.edit_text("📤 Отправляю видео...")

    await msg.answer_video(
        types.FSInputFile(final_path),
        caption="✅ Готово! Видео со звуком.",
        supports_streaming=True
    )

    await msg.answer("⬇️ Хочешь ещё?", reply_markup=after_download_kb())

    # 5️⃣ ЧИСТКА
    for f in [video_path, audio_path, final_path]:
        try:
            os.remove(f)
        except:
            pass

    try:
        await status.delete()
    except:
        pass

# ================== RUN ==================

async def main():
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
