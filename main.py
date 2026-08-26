import os
import requests
import asyncio
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot 24/7 Alive!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Universal API (Render IP-sini blokdan a?la?ar)
def get_cobalt_media(url, is_audio=False):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "downloadMode": "audio" if is_audio else "auto",
        "videoQuality": "720"
    }
    
    # Durnukly API serwerleri
    api_urls = [
        "https://api.cobalt.tools/",
        "https://cobalt-api.kwiatek.xyz/"
    ]
    
    for api in api_urls:
        try:
            res = requests.post(api, json=payload, headers=headers, timeout=12).json()
            if res.get("status") in ["redirect", "tunnel", "picker"]:
                return res.get("url") or (res.get("picker")[0].get("url") if res.get("picker") else None)
        except Exception as e:
            print(f"Cobalt Error ({api}): {e}")
            
    return None

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Salam! TikTok, Instagram, YouTube ?a-da Pornhub linkini ugrat, men sa?a media g???rip bere?in.")

@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    url = message.text.strip()
    wait_msg = await message.answer("?? ??klen??r, bir az gara?y?...")

    loop = asyncio.get_event_loop()
    video_url = await loop.run_in_executor(None, get_cobalt_media, url, False)

    if video_url:
        try:
            builder = InlineKeyboardBuilder()
            builder.button(text="Hawa ??", callback_data="aud_yes")
            builder.button(text="?ok ?", callback_data="aud_no")
            
            await message.answer_video(
                video=video_url, 
                caption=f"?? Media g???rildi!\n\nVideodaky a?dymy hem g???rip bere?inmi?",
                reply_markup=builder.as_markup()
            )
            await wait_msg.delete()
        except Exception as e:
            print(f"Telegram Send Error: {e}")
            await wait_msg.edit_text("? Wideony Telegram-a ugratmakda n?sazlyk d?r?di (g?wr?mi ?r?n uly bolmagy m?mkin).")
    else:
        await wait_msg.edit_text("? Mediany g???rip bolmady. Linki? dogrylygyny barla?.")

@dp.callback_query(F.data == "aud_no")
async def handle_no(call: types.CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("Bolsun!")

@dp.callback_query(F.data == "aud_yes")
async def handle_audio(call: types.CallbackQuery):
    await call.message.edit_reply_markup(reply_markup=None)
    status_msg = await call.message.answer("?? A?dym g???ril??r...")
    
    # Caption-dan linki tapmak
    url = None
    for entity in call.message.caption_entities or []:
        if entity.type == "url":
            url = call.message.caption[entity.offset:entity.offset+entity.length]
            
    if not url:
        # User-i? ??ki ugradan linkini text-den almak
        url = call.message.reply_to_message.text if call.message.reply_to_message else None

    if url:
        loop = asyncio.get_event_loop()
        audio_url = await loop.run_in_executor(None, get_cobalt_media, url, True)
        
        if audio_url:
            try:
                await call.message.answer_audio(audio=audio_url, caption="?? A?dym g???rildi!")
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit_text("? A?dymy Telegram-a ugratmakda n?sazlyk d?r?di.")
        else:
            await status_msg.edit_text("? A?dymy alyp bolmady.")
    else:
        await status_msg.edit_text("? Link tapylmady.")
        
    await call.answer()

async def main():
    Thread(target=run_flask).start()
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
