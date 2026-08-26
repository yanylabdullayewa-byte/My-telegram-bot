import os
import glob
import asyncio
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

# ?hli sa?tlar (TikTok, IG, YT, Pornhub) ??in durnukly yt-dlp funksi?asy
def download_media(url: str, download_type: str = "video"):
    for f in glob.glob("downloaded_*"):
        try:
            os.remove(f)
        except:
            pass

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    if download_type == "audio":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': 'downloaded_audio.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': 'downloaded_video.mp4',
        })

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
    wait_msg = await message.answer("?? Serwere g???ril??r, bir az gara?y?...")

    try:
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, download_media, url, "video")

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
            await wait_msg.edit_text("? Mediany g???rip bolmady. Linki barla?.")

    except Exception as e:
        print(f"Error: {e}")
        await wait_msg.edit_text("? ?al?y?lyk d?r?di. Wideo g???rilmedi.")

@dp.callback_query(F.data == "aud_no")
async def handle_no(call: types.CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Bolsun!")

@dp.callback_query(F.data == "aud_yes")
async def handle_yt_audio(call: types.CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)
    status_msg = await call.message.answer("?? A?dym g???ril??r...")
    
    url = call.message.caption
    for entity in call.message.caption_entities or []:
        if entity.type == "url":
            url = call.message.caption[entity.offset:entity.offset+entity.length]
            
    try:
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, download_media, url, "audio")
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
