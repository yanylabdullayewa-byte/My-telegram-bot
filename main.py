import os
import glob
import asyncio
import requests
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
import yt_dlp

TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 24/7 Alive!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# TikTok ??in ??rite API funksi?asy (IP bloky a?lamak ??in)
def get_tiktok_data(url):
    try:
        api_url = f"https://tikwm.com/api/?url={url}"
        res = requests.get(api_url, timeout=10).json()
        if res.get("code") == 0:
            data = res["data"]
            return {
                "video": data.get("play"),
                "audio": data.get("music"),
                "title": data.get("title", "TikTok Video")
            }
    except Exception as e:
        print(f"TikTok API Error: {e}")
    return None

# Gala? sa?tlar ??in yt-dlp funksi?asy
def download_yt_dlp(url: str, download_type: str = "video"):
    for f in glob.glob("downloaded_*"):
        try:
            os.remove(f)
        except:
            pass

    if download_type == "audio":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloaded_audio.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
    else:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': 'downloaded_video.mp4',
            'quiet': True,
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Media')
        
    if download_type == "audio":
        files = glob.glob("downloaded_audio.*")
        return (files[0] if files else None), title
    else:
        files = glob.glob("downloaded_video.*")
        return (files[0] if files else None), title

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Salam! Link ugrady? (TikTok, Instagram, YouTube, Pornhub), men media g???rip bere?in.")

@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    url = message.text.strip()
    wait_msg = await message.answer("?? ??klen??r, bir az gara?y?...")

    try:
        # 1. Eger TikTok bolsa TikWM API ulan?arys
        if "tiktok.com" in url:
            tt_data = get_tiktok_data(url)
            if tt_data and tt_data.get("video"):
                builder = InlineKeyboardBuilder()
                builder.button(text="Hawa ??", callback_data=f"ttaud_yes|{url}")
                builder.button(text="?ok ?", callback_data="aud_no")

                await message.answer_video(
                    video=tt_data["video"],
                    caption=f"?? <b>{tt_data['title']}</b>\n\nVideodaky a?dymy hem g???rip bere?inmi?",
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
                await wait_msg.delete()
                return
            else:
                await wait_msg.edit_text("? TikTok videosy alynmady.")
                return

        # 2. Galan ?hli sa?tlar ??in yt-dlp ulan?arys
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, download_yt_dlp, url, "video")

        if file_path and os.path.exists(file_path):
            await wait_msg.edit_text("?? Telegram-a ??klen??r...")
            video_file = FSInputFile(file_path)
            
            builder = InlineKeyboardBuilder()
            builder.button(text="Hawa ??", callback_data="aud_yes")
            builder.button(text="?ok ?", callback_data="aud_no")
            
            await message.answer_video(
                video=video_file, 
                caption=f"?? <b>{title}</b>\n\nVideodaky a?dymy hem g???rip bere?inmi?",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            await wait_msg.delete()
            os.remove(file_path)
        else:
            await wait_msg.edit_text("? Mediany g???rip bolmady.")

    except Exception as e:
        print(f"Error: {e}")
        await wait_msg.edit_text("? ?al?y?lyk d?r?di.")

# Knopkalar ??in handlers
@dp.callback_query(F.data == "aud_no")
async def handle_no(call: types.CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Bolsun!")

@dp.callback_query(F.data.startswith("ttaud_yes"))
async def handle_tt_audio(call: types.CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)
    status_msg = await call.message.answer("?? A?dym g???ril??r...")
    url = call.data.split("|")[1]
    tt_data = get_tiktok_data(url)
    if tt_data and tt_data.get("audio"):
        await call.message.answer_audio(audio=tt_data["audio"], caption=f"?? {tt_data['title']}")
        await status_msg.delete()
    else:
        await status_msg.edit_text("? A?dym tapylmady.")
    await call.answer()

@dp.callback_query(F.data == "aud_yes")
async def handle_yt_audio(call: types.CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)
    status_msg = await call.message.answer("?? A?dym g???ril??r...")
    
    # Linki caption-dan almak
    url = call.message.caption
    for entity in call.message.caption_entities or []:
        if entity.type == "url":
            url = call.message.caption[entity.offset:entity.offset+entity.length]
            
    try:
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, download_yt_dlp, url, "audio")
        if file_path and os.path.exists(file_path):
            audio_file = FSInputFile(file_path)
            await call.message.answer_audio(audio=audio_file, caption=f"?? {title}")
            await status_msg.delete()
            os.remove(file_path)
        else:
            await status_msg.edit_text("? A?dymy alyp bolmady.")
    except Exception as e:
        await status_msg.edit_text("? N?sazlyk d?r?di.")
    await call.answer()

async def main():
    Thread(target=run_flask).start()
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
