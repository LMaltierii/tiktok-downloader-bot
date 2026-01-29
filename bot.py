import asyncio
import os
import uuid
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================== CONFIG ==================

MAX_PARALLEL_DOWNLOADS = 2   
DOWNLOAD_TIMEOUT = 600       
MAX_FILE_MB = 49

download_semaphore = asyncio.Semaphore(MAX_PARALLEL_DOWNLOADS)

# ================= UI =================

def main_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬇️ Скачать видео", callback_data="download")],
            [InlineKeyboardButton(text="⭐ Поделиться ботом", switch_inline_query="")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
        ]
    )

def after_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬇️ Скачать ещё", callback_data="download")],
            [InlineKeyboardButton(text="⭐ Поделиться ботом", switch_inline_query="")],
        ]
    )

def back_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
        ]
    )

# ================= SCREENS =================

def screen_home():
    return (
        "🎬 *TikTokBroBot*\n\n"
        "Пришли ссылку на видео и я скачаю его.\n\n"
        "Поддержка:\n"
        "• TikTok\n"
        "• YouTube Shorts\n"
        "• Reels"
    )

def screen_wait_link():
    return (
        "🔗 *Пришли ссылку на видео*\n\n"
        "Я поддерживаю:\n"
        "• TikTok\n"
        "• YouTube Shorts\n"
        "• Reels"
    )

# ================= STATE =================

waiting_users = set()
active_users = set()

# ================= START =================

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(screen_home(), reply_markup=main_kb(), parse_mode="Markdown")

# ================= CALLBACKS =================

@dp.callback_query(F.data == "download")
async def download_cb(cb: types.CallbackQuery):
    waiting_users.add(cb.from_user.id)
    await cb.message.edit_text(screen_wait_link(), reply_markup=back_kb(), parse_mode="Markdown")
    await cb.answer()

@dp.callback_query(F.data == "back")
async def back_cb(cb: types.CallbackQuery):
    waiting_users.discard(cb.from_user.id)
    await cb.message.edit_text(screen_home(), reply_markup=main_kb(), parse_mode="Markdown")
    await cb.answer()

@dp.callback_query(F.data == "help")
async def help_cb(cb: types.CallbackQuery):
    await cb.message.edit_text(
        "ℹ️ *Как пользоваться ботом:*\n\n"
        "1. Нажми «Скачать видео»\n"
        "2. Пришли ссылку\n"
        "3. Получи файл\n\n"
        "⚡ Быстро и просто.",
        reply_markup=back_kb(),
        parse_mode="Markdown",
    )
    await cb.answer()

# ================= UTILS =================

def detect_platform(url: str) -> str:
    url = url.lower()
    if "tiktok" in url:
        return "TikTok"
    if "youtube" in url or "youtu.be" in url:
        return "YouTube"
    if "instagram" in url or "reels" in url:
        return "Instagram"
    return "Видео"

# ================= CLEANUP TASK =================

async def cleanup_loop():
    while True:
        now = time.time()
        for f in os.listdir(DOWNLOAD_DIR):
            path = os.path.join(DOWNLOAD_DIR, f)
            try:
                if os.path.isfile(path):
                    if now - os.path.getmtime(path) > 3600:
                        os.remove(path)
                        print("[CLEANUP] removed", path)
            except:
                pass
        await asyncio.sleep(1800)

# ================= MAIN =================

@dp.message()
async def handle_link(msg: types.Message):
    user_id = msg.from_user.id

    if user_id not in waiting_users:
        return

    if user_id in active_users:
        await msg.answer("⏳ Подожди, предыдущее видео ещё обрабатывается.")
        return

    url = msg.text.strip()
    if not url.startswith("http"):
        await msg.answer("❌ Это не ссылка.")
        return

    waiting_users.discard(user_id)
    active_users.add(user_id)

    platform = detect_platform(url)

    status = await msg.answer(f"🔎 Анализирую ссылку ({platform})...")

    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    cmd = [
        "python", "-m", "yt_dlp",
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "--concurrent-fragments", "4",
        "--no-playlist",
        "-o", output_template,
        url
    ]

    print(f"[DOWNLOAD] user={user_id} platform={platform}")

    try:
        async with download_semaphore:
            await status.edit_text("📥 Скачиваю видео...")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=DOWNLOAD_TIMEOUT)
            except asyncio.TimeoutError:
                process.kill()
                await status.edit_text("⏰ Таймаут при скачивании.", reply_markup=main_kb())
                return

            if process.returncode != 0:
                print(stdout.decode())
                print(stderr.decode())
                await status.edit_text(
                    "⚠️ *Не удалось скачать видео.*",
                    parse_mode="Markdown",
                    reply_markup=main_kb()
                )
                return

    except Exception as e:
        print("ERROR:", e)
        await status.edit_text("❌ Ошибка при обработке видео.", reply_markup=main_kb())
        return

    finally:
        active_users.discard(user_id)

    # ================= FIND FILE =================

    downloaded_file = None
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(file_id) and f.lower().endswith(".mp4"):
            downloaded_file = os.path.join(DOWNLOAD_DIR, f)
            break

    if not downloaded_file:
        await status.edit_text("❌ Не удалось получить файл.", reply_markup=main_kb())
        return

    # ================= SIZE CHECK =================

    size_mb = os.path.getsize(downloaded_file) / 1024 / 1024
    if size_mb > MAX_FILE_MB:
        await status.edit_text("❌ Видео слишком большое для отправки.")
        os.remove(downloaded_file)
        return

    # ================= SEND =================

    await status.edit_text("📤 Отправляю файл...")

    await msg.answer_video(
        types.FSInputFile(downloaded_file),
        caption="💾 Скачано через @TikTokDBroBot",
        supports_streaming=True
    )

    await status.edit_text(
        "✅ *Готово!*\n\nВидео успешно скачано.",
        reply_markup=after_kb(),
        parse_mode="Markdown"
    )

    try:
        os.remove(downloaded_file)
    except:
        pass

# ================= RUN =================

async def main():
    print("TikTokDBroBot PRODUCTION started...")
    asyncio.create_task(cleanup_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
