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
            [InlineKeyboardButton(text="⭐ Поделиться ботом", switch_inline_query="")],
        ]
    )


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
        "👋 *Добро пожаловать в TikTokDBroBot!*\n\n"
        "🎬 Я скачиваю видео из:\n"
        "• TikTok\n"
        "• YouTube Shorts\n"
        "• Reels\n\n"
        "Просто пришли ссылку на видео 👇",
        reply_markup=start_kb(),
        parse_mode="Markdown",
    )


# ================== HELP ==================


@dp.callback_query(lambda c: c.data == "help_download")
async def help_download_cb(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⬇️ *Как скачать видео:*\n\n"
        "1️⃣ Скопируй ссылку на видео\n"
        "2️⃣ Вставь её в этот чат\n"
        "3️⃣ Подожди пару секунд\n"
        "4️⃣ Получи готовое видео со звуком\n\n"
        "⚡ Просто вставь ссылку — и всё!",
        parse_mode="Markdown",
        reply_markup=start_kb(),
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "help_about")
async def help_about_cb(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ *О боте:*\n\n"
        "🤖 TikTokDBroBot — бот для скачивания видео.\n\n"
        "✅ Поддерживает:\n"
        "• TikTok\n"
        "• YouTube Shorts\n"
        "• Reels\n\n"
        "📏 Ограничения:\n"
        "• Видео до 3 минут\n \n"
        "🚀 Просто вставь ссылку!",
        parse_mode="Markdown",
        reply_markup=start_kb(),
    )
    await callback.answer()


# ================== AGAIN BUTTON ==================


@dp.callback_query(lambda c: c.data == "again")
async def again_cb(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass

    await bot.send_message(
        callback.from_user.id, "🔗 Просто пришли новую ссылку на видео:"
    )
    await callback.answer()


# ================== MAIN ==================


@dp.message()
async def handle_link(msg: types.Message):
    if not msg.text:
        return

    url = msg.text.strip()

    if not url.startswith("http"):
        await msg.answer("❌ Это не похоже на ссылку.")
        return

    status_msg = await msg.answer("⏳ Проверяю видео...")

    # ================= CHECK DURATION =================

    try:
        check = subprocess.run(
            ["python", "-m", "yt_dlp", "--print", "%(duration)s", url],
            capture_output=True,
            text=True,
            timeout=30,
        )

        try:
            duration = int(float(check.stdout.strip()))
        except:
            duration = 9999

        if duration > 180:
            await status_msg.edit_text(
                "⚠️ Поддерживаются только короткие видео (до 3 минут)."
            )
            return

    except:
        await status_msg.edit_text("❌ Не удалось проверить видео.")
        return

    # ================= DOWNLOAD =================

    await status_msg.edit_text("📥 Скачиваю и склеиваю видео...")

    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    is_tiktok = "tiktok.com" in url.lower()

    if is_tiktok:
        cmd = [
            "python",
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--merge-output-format",
            "mp4",
            "--recode-video",
            "mp4",
            "--user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "--referer",
            "https://www.tiktok.com/",
            "-o",
            output_template,
            url,
        ]
        cmd = [
            "python",
            "-m",
            "yt_dlp",
            "-f",
            "bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "--recode-video",
            "mp4",
            "--postprocessor-args",
            "ffmpeg:-c:v copy -c:a aac",
            "--no-playlist",
            "-o",
            output_template,
            url,
        ]

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if process.returncode != 0:
            print(process.stdout)
            print(process.stderr)
            await status_msg.edit_text("❌ Ошибка при скачивании видео.")
            return

    except Exception as e:
        print("DOWNLOAD ERROR:", e)
        await status_msg.edit_text("❌ Ошибка при скачивании.")
        return

    # ================= FIND FILE =================

    downloaded_file = None
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(file_id) and f.lower().endswith(".mp4"):
            downloaded_file = os.path.join(DOWNLOAD_DIR, f)
            break

    if not downloaded_file:
        await status_msg.edit_text("❌ Не удалось получить mp4 файл.")
        return

    # ================= SIZE CHECK =================

    size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
    if size_mb > 48:
        os.remove(downloaded_file)
        await status_msg.edit_text("⚠️ Видео слишком большое для Telegram.")
        return

    # ================= SEND =================

    await status_msg.edit_text("📤 Отправляю видео...")

    await msg.answer_video(
        types.FSInputFile(downloaded_file),
        caption="💾 Скачано через @TikTokDBroBot\n⬇️ Скачивай видео без водяных знаков",
        supports_streaming=True,
        request_timeout=1200,
    )

    try:
        await status_msg.delete()
    except:
        pass

    await msg.answer(
        "✅ *Готово!*\n\n📥 Видео скачано со звуком.",
        reply_markup=after_download_kb(),
        parse_mode="Markdown",
    )

    # ================= CLEAN =================

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
