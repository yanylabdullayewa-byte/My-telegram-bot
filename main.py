import asyncio
import logging
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

import requests
import yt_dlp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from flask import Flask

MAX_FILE_BYTES = 50 * 1024 * 1024
OWNER_LINK = os.getenv("BOT_OWNER_LINK", "t.me/ikramromanow")
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("telegram-video-bot")

app = Flask(__name__)


@app.get("/")
def home() -> tuple[str, int]:
    return "Telegram video bot is running.", 200


@app.get("/healthz")
def healthz() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.get("/api/healthz")
def api_healthz() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


def run_health_server() -> None:
    app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)


def start_health_server() -> None:
    Thread(target=run_health_server, daemon=True, name="health-server").start()


def supported_platform(raw_url: str) -> str | None:
    try:
        parsed = urlparse(raw_url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None

    hostname = (parsed.hostname or "").lower().removeprefix("www.")
    if hostname == "tiktok.com" or hostname.endswith(".tiktok.com"):
        return "TikTok"
    if hostname == "instagram.com" or hostname.endswith(".instagram.com"):
        return "Instagram"
    if (
        hostname == "youtube.com"
        or hostname.endswith(".youtube.com")
        or hostname == "youtu.be"
    ):
        return "YouTube"
    return None


def caption(title: str) -> str:
    clean_title = re.sub(r"\s+", " ", title).strip()[:900] or "Video"
    return f"{clean_title}\n\nBot eýesi: {OWNER_LINK}"


def get_tiktok(raw_url: str) -> tuple[str, str, str | None] | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    # 1. ?ol: TikWM API arkaly barla?arys
    try:
        api_url = "https://tikwm.com/api/"
        response = requests.get(api_url, params={"url": raw_url, "hd": "1"}, headers=headers, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("code") == 0 and "data" in res_json:
                data = res_json["data"]
                video_url = data.get("play") or data.get("wmplay")
                music_url = data.get("music")
                title = data.get("title", "TikTok Video")
                if video_url:
                    return video_url, title, music_url
    except Exception as e:
        print(f"TikWM API Error: {e}")

    # 2. ?ol (?ti?a?lyk): Eger TikWM i?lemes?, LoFi API arkaly barla?arys
    try:
        backup_url = f"https://api.douyin.wtf/api?url={raw_url}"
        response = requests.get(backup_url, headers=headers, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            video_url = res_json.get("nwm_video_url") or res_json.get("video_data", {}).get("nwm_video_url")
            title = res_json.get("desc", "TikTok Video")
            if video_url:
                return video_url, title, None
    except Exception as e:
        print(f"Backup API Error: {e}")

    return None
    
def download_with_ytdlp(raw_url: str) -> tuple[Path, str, Path]:
    job_dir = Path(tempfile.mkdtemp(prefix="telegram-video-"))
    output_template = str(job_dir / "%(id)s.%(ext)s")
    options = {
        "format": "best[ext=mp4][filesize<50M]/best[filesize<50M]/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "max_filesize": "50M",
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(raw_url, download=True)
        files = [
            item
            for item in job_dir.iterdir()
            if item.is_file() and not item.name.endswith((".part", ".ytdl"))
        ]
        if not files:
            raise RuntimeError("yt-dlp did not create a video file")
        file_path = files[0]
        if file_path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("video is larger than Telegram's 50 MB limit")
        return file_path, info.get("title") or "Video", job_dir
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise


def download_audio_with_ytdlp(raw_url: str) -> tuple[Path, Path]:
    job_dir = Path(tempfile.mkdtemp(prefix="telegram-audio-"))
    output_template = str(job_dir / "%(id)s.%(ext)s")
    options = {
        "format": "bestaudio[filesize<50M]/bestaudio",
        "outtmpl": output_template,
        "max_filesize": "50M",
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.extract_info(raw_url, download=True)
        files = [
            item
            for item in job_dir.iterdir()
            if item.is_file() and not item.name.endswith((".part", ".ytdl"))
        ]
        if not files:
            raise RuntimeError("yt-dlp did not create an audio file")
        if files[0].stat().st_size > MAX_FILE_BYTES:
            raise ValueError("audio is larger than Telegram's 50 MB limit")
        return files[0], job_dir
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise


dp = Dispatcher()


@dataclass
class DownloadJob:
    chat_id: int
    raw_url: str
    platform: str
    video_ready: asyncio.Event
    video_result: tuple[Path, str, Path] | None = None
    tiktok_music_url: str | None = None
    audio_requested: bool = False
    audio_sent: bool = False


jobs: dict[str, DownloadJob] = {}


def audio_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Hawa", callback_data=f"audio:yes:{job_id}"),
                InlineKeyboardButton(text="Ýok", callback_data=f"audio:no:{job_id}"),
            ]
        ]
    )


@dp.message(CommandStart())
async def start_handler(message: types.Message) -> None:
    await message.answer(
        "Salam! TikTok, Instagram ýa-da YouTube ssylkasyny iberiň, "
        "men wideosyny ýüklemäge synanyşaryn."
    )


@dp.message(F.text)
def handle_message(message: types.Message):
    url = message.text.strip()
    
    if "tiktok.com" in url:
        msg = message.answer("Wait...")
        res = get_tiktok(url)
        
        if res:
            video_url, title, music_url = res
            try:
                # Wideony g?ni linkden Telegram-a ugrat?arys
                message.answer_video(video=video_url, caption=f"?? {title}")
                
                # Eger a?dymy hem bar bolsa, ony hem ugrat?arys
                if music_url:
                    message.answer_audio(audio=music_url, caption="?? TikTok Audio")
            except Exception as e:
                print(f"Send error: {e}")
                message.answer("Videony Telegram-a ugratmakda ?al?y?lyk ?ykdy.")
        else:
            message.answer("Videony skachat edip bolmady. Linki barla?.")


@dp.callback_query(F.data.startswith("audio:"))
async def audio_choice(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Bu düwme indi güýjünde däl.", show_alert=True)
        return

    choice, job_id = parts[1], parts[2]
    job = jobs.get(job_id)
    if not job:
        await callback.answer("Wideo işi tamamlandy ýa-da möhleti geçdi.", show_alert=True)
        return

    await callback.answer("Saýlawyňyz kabul edildi.")
    await callback.message.edit_reply_markup(reply_markup=None)
    if choice == "no":
        return

    job.audio_requested = True
    await job.video_ready.wait()
    if job.audio_sent:
        return
    job.audio_sent = True

    try:
        if job.platform == "TikTok":
            if not job.tiktok_music_url:
                await callback.message.answer("Bu TikTok wideoda aýdym çeşmesi tapylmady.")
                return
            await callback.message.answer_audio(
                audio=job.tiktok_music_url,
                caption="Wideonyň aýdym ýazgysy",
            )
            return

        audio_path, audio_dir = await asyncio.to_thread(
            download_audio_with_ytdlp, job.raw_url
        )
        try:
            await callback.message.answer_audio(
                audio=FSInputFile(audio_path),
                caption="Wideonyň aýdym ýazgysy",
            )
        finally:
            shutil.rmtree(audio_dir, ignore_errors=True)
    except Exception:
        logger.exception("Audio download failed for %s", job.platform)
        await callback.message.answer("Wideonyň aýdymyny alyp bolmady.")


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN Replit Secret hökman goşulmaly.")

    start_health_server()
    bot = Bot(token=token)
    logger.info("Starting Telegram bot")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
