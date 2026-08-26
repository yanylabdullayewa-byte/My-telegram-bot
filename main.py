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

# Render ??in Flask Server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 24/7 Alive!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Wideo we ses g???rmek ??in yt-dlp funksi?asy
def download_media(url: str, download_type: str = "video"):
    # ??ki galan wagtla?yn fa?llary arassalamak
    for f in glob.glob("downloaded_*"):
        try:
            os.remove(f)
        except:
            pass

    outtmpl = "downloaded_%(id)s.%(ext)s"
    
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
            'no_warnings': True,
        }
    else:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': 'downloaded_video.mp4',
            'quiet': True,
            'no_warnings': True,
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

# /start komandasy
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Salam! TikTok, Instagram, YouTube ?a-da Pornhub linkini ugrat, men sa?a media g???rip bere?in.")

# Link gelende i?le??n b?l?m
@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    url = message.text.strip()
    wait_msg = await message.answer("?? Media serwere g???ril??r, bir az gara?y?...")

    try:
        # Loop-y? i?inde agyr i?i a?ratyn potokda i?letmek
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, download_media, url, "video")

        if file_path and os.path.exists(file_path):
            await wait_msg.edit_text("?? Telegram-a ??klen??r...")
            
            # Wideo ugratmak
            video_file = FSInputFile(file_path)
            
            # A?dym sorag knopkalaryny d?retmek
            builder = InlineKeyboardBuilder()
            builder.button(text="Hawa ??", callback_data=f"aud_yes|{url[:50]}")
            builder.button(text="?ok ?", callback_data="aud_no")
            
            await message.answer_video(
                video=video_file, 
                caption=f"?? <b>{title}</b>\n\nVideodaky a?dymy hem g???rip bere?inmi?",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            await wait_msg.delete()
            
            # Fa?ly serwerden pozmak
            os.remove(file_path)
        else:
            await wait_msg.edit_text("? Mediany g???rip bolmady. Linki barla?.")

    except Exception as e:
        print(f"Error: {e}")
        await wait_msg.edit_text("? ?al?y?lyk d?r?di ?a-da sa?t b?kdeldi.")

# Knopka basylanda (Hawa / ?ok)
@dp.callback_query(F.data.startswith("aud_"))
async def handle_audio_choice(call: types.CallbackQuery):
    data = call.data
    
    if data == "aud_no":
        await call.message.edit_reply_markup(reply_markup=None)
        await call.answer("Bolsun, a?dym g???rilmedi.")
    else:
        await call.message.edit_reply_markup(reply_markup=None)
        status_msg = await call.message.answer("?? A?dym g???ril??r...")
        
        # Linki text-den ga?tadan almak
        url = call.message.text or call.message.caption
        
        try:
            loop = asyncio.get_event_loop()
            # Bot entity-den linki tapmak
            for entity in call.message.caption_entities or []:
                if entity.type == "url":
                    url = call.message.caption[entity.offset:entity.offset+entity.length]
            
            file_path, title = await loop.run_in_executor(None, download_media, url, "audio")
            
            if file_path and os.path.exists(file_path):
                audio_file = FSInputFile(file_path)
                await call.message.answer_audio(audio=audio_file, caption=f"?? {title}")
                await status_msg.delete()
                os.remove(file_path)
            else:
                await status_msg.edit_text("? A?dymy a?ratyn alyp bolmady.")
        except Exception as e:
            print(f"Audio Error: {e}")
            await status_msg.edit_text("? A?dymy g???rmekde ?al?y?lyk ?ykdy.")
            
    await call.answer()

async def main():
    Thread(target=run_flask).start()
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
