import asyncio
import os
import uuid
import subprocess

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================== KEYBOARDS ==================


def after_download_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬇️ Скачать ещё", callback_data="again")],
            [InlineKeyboardButton(text="⭐ Поделиться ботом", switch_inline_query="")],
        ]
    )


# ================== START ==================


@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "👋 Пришли ссылку на TikTok / YouTube Shorts / Reels — я пришлю файл.\n\n"
        "Просто вставь ссылку в чат."
    )


# ================== AGAIN BUTTON ==================


@dp.callback_query(F.data == "again")
async def again_cb(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass

    await bot.send_message(callback.from_user.id, "🔗 Просто пришли ссылку на видео:")
    await callback.answer()


# ================== MAIN ==================


@dp.message()
async def handle_link(msg: types.Message):
    url = msg.text.strip()

    if not url.startswith("http"):
        await msg.answer("❌ Это не похоже на ссылку.")
        return

    status_msg = await msg.answer("⏳ Проверяю видео...")

    # ========== CHECK DURATION (120 sec limit) ==========
    check = subprocess.run(
        ["python", "-m", "yt_dlp", "--print", "%(duration)s", url],
        capture_output=True,
        text=True,
    )

    try:
        duration = int(float(check.stdout.strip()))
    except:
        duration = 9999

    if duration > 120:
        await status_msg.edit_text(
            "⚠️ Поддерживаются только короткие видео (до 2 минут).\n\n"
            "Это видео слишком длинное."
        )
        return

    # ========== DOWNLOAD ==========
    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    is_tiktok = "tiktok.com" in url.lower()

    await status_msg.edit_text("📥 Скачиваю видео...")

    if is_tiktok:
        cmd = [
            "python",
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--merge-output-format",
            "mp4",
            "--user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "--referer",
            "https://www.tiktok.com/",
            "-o",
            output_template,
            url,
        ]
    else:
        # YouTube Shorts / Reels
        cmd = [
            "python",
            "-m",
            "yt_dlp",
            "-f",
            "bv*[height<=720]+ba/b[height<=720]",
            "--no-playlist",
            "--merge-output-format",
            "mp4",
            "-o",
            output_template,
            url,
        ]

    process = subprocess.run(cmd, capture_output=True, text=True)

    if process.returncode != 0:
        print(process.stdout)
        print(process.stderr)
        await status_msg.edit_text("❌ Ошибка при скачивании видео.")
        return

    # ========== FIND FILE ==========
    downloaded_file = None
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(file_id):
            downloaded_file = os.path.join(DOWNLOAD_DIR, f)
            break

    if not downloaded_file:
        await status_msg.edit_text("❌ Файл не найден после скачивания.")
        return

    # ========== SIZE CHECK ==========
    size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
    if size_mb > 45:
        os.remove(downloaded_file)
        await status_msg.edit_text("⚠️ Видео слишком большое для Telegram.")
        return

    # ========== SEND ==========
    await status_msg.edit_text("📤 Отправляю файл...")

    try:
        await msg.answer_document(
            types.FSInputFile(downloaded_file),
            caption=(
                "💾 Скачано через @TikTokDBroBot\n⬇️ Скачивай видео без водяных знаков"
            ),
            request_timeout=1200,
        )
    except Exception as e:
        print("SEND ERROR:", e)
        await status_msg.edit_text("❌ Ошибка при отправке в Telegram.")
        return

    try:
        await status_msg.delete()
    except:
        pass

    await bot.send_message(
        msg.from_user.id,
        "✅ *Готово!*\n\n📥 Видео успешно скачано.\n🔗 Можешь прислать ещё ссылку.",
        reply_markup=after_download_kb(),
        parse_mode="Markdown",
    )

    # ========== CLEAN ==========
    try:
        os.remove(downloaded_file)
    except:
        pass


# ================== RUN ==================


async def main():
    print("Video Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
