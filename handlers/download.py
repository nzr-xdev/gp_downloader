from aiogram import Router, F
from aiogram.types import FSInputFile, CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import os, asyncio
from core.ssyd import URLParser, GPDownloader
from handlers.start import LOCALIZATION, get_back_keyboard
import config
from mutagen.id3 import ID3
from database.db_handler import db

class DownloadStates(StatesGroup):
    confirm_download = State()

router = Router()
parser = URLParser()
downloader = GPDownloader()

async def start_actual_download(message: Message, download_data: dict, lang: str, user_status: str, user_id: int):
    status_msg = await message.answer(text=LOCALIZATION[lang]["processing"], parse_mode="Markdown")
    limits = config.get_plan_limits(user_status)
    max_timeout = limits.get("max_timeout_per_request", 180)
    max_length = limits.get("max_length_per_song", 10)
    
    try:
        for url, (platform, mediatype) in download_data.items():
            try:
                output_files = await asyncio.wait_for(
                    asyncio.to_thread(downloader.process, url, platform, mediatype, max_length * 60),
                    timeout=max_timeout
                )
            except asyncio.TimeoutError:
                await db.track_error()
                await status_msg.edit_text(LOCALIZATION[lang].get("error_timeout"), parse_mode="Markdown")
                return
            except Exception as e:
                if "too long" in str(e).lower() or "duration" in str(e).lower():
                    await status_msg.edit_text(LOCALIZATION[lang].get("error_too_long").format(max_len=max_length), parse_mode="Markdown")
                    return
                raise e
            
            for file_path in output_files:
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    await status_msg.edit_text(LOCALIZATION[lang]["uploading"].format(filename=filename), parse_mode="Markdown")
                    audio_file = FSInputFile(file_path)
                    thumb_path = f"{file_path}.jpg"
                    thumb_file = None
                    
                    try:
                        tags = ID3(file_path)
                        for key in tags.keys():
                            if key.startswith('APIC'):
                                with open(thumb_path, 'wb') as img_file:
                                    img_file.write(tags[key].data)
                                thumb_file = FSInputFile(thumb_path)
                                break
                    except Exception as e:
                        print(f"⚠️ Unable to extract thumbnail for Telegram: {e}")
                    
                    await message.answer_audio(audio=audio_file, thumbnail=thumb_file)
                    await db.track_download(user_id, 1)
                    
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    if os.path.exists(thumb_path):
                        os.remove(thumb_path)
                        
        await status_msg.delete()
        menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=LOCALIZATION[lang]["main_menu"]["button"], callback_data=f"main_menu_{lang}")]])
        await message.answer(LOCALIZATION[lang]["success_text"], reply_markup=menu_keyboard, parse_mode="Markdown")
    except Exception as e:
        await db.track_error()
        print(f"💥 DOWNLOAD EXECUTION CRASHED: {e}")
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=LOCALIZATION[lang]["back"], callback_data=f"main_menu_{lang}")]])
        error_msg = LOCALIZATION[lang].get("error_msg", "An error occurred:")
        await message.answer(f"{error_msg}\n`{str(e)}`", reply_markup=back_keyboard, parse_mode="Markdown")

@router.message(F.text)
async def handle_download(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await db.register_user(user_id)
    user_data = await db.get_user(user_id)
    user_status = user_data.get("status", "user") if user_data else "user"
    
    switches = config.get_switches()
    
    state_data = await state.get_data()
    saved_lang = state_data.get("user_lang")
    lang = saved_lang if saved_lang else (message.from_user.language_code if message.from_user.language_code in LOCALIZATION else "en")

    if switches["maintenance_mode"] and user_status != "admin":
        await message.answer(LOCALIZATION[lang].get("error_maintenance"), reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
        return

    limits = config.get_plan_limits(user_status)
    max_songs_per_day = limits.get("max_songs_per_day", 30)
    daily_downloads = user_data.get("daily_downloads", 0) if user_data else 0

    if daily_downloads >= max_songs_per_day and user_status != "admin":
        await message.answer(LOCALIZATION[lang].get("error_daily_limit_exceeded").format(max_day=max_songs_per_day), reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
        return

    try:
        result, total_count = parser.link_preparer(message.text)
    except Exception as e:
        print(f"❌ Parsing failed or no links found: {e}")
        await message.answer(LOCALIZATION[lang].get("error_unknown_command"), reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
        return

    if total_count == 0:
        return

    filtered_result = {}
    disabled_platforms = set()
    for url, (platform, mediatype) in result.items():
        if not switches.get(f"module_{platform}", True):
            disabled_platforms.add(platform)
        else:
            filtered_result[url] = (platform, mediatype)

    if disabled_platforms:
        if total_count == 1:
            plat = list(disabled_platforms)[0]
            await message.answer(LOCALIZATION[lang].get("error_platform_disabled_single").format(platform=plat), reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
            return
        else:
            plat_str = ", ".join(disabled_platforms)
            await message.answer(LOCALIZATION[lang].get("error_platform_disabled_bulk").format(platform=plat_str), parse_mode="Markdown")
            result = filtered_result
            total_count = len(result)
            if total_count == 0:
                return

    max_songs_per_request = limits.get("max_songs_per_request", 5)
    if total_count > max_songs_per_request:
        await message.answer(LOCALIZATION[lang].get("error_too_many_songs").format(max_songs=max_songs_per_request), reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
        return

    if daily_downloads + total_count > max_songs_per_day and user_status != "admin":
        await message.answer(LOCALIZATION[lang].get("error_packet_exceeds_daily").format(remains=max_songs_per_day - daily_downloads), reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
        return

    if total_count > 1:
        await state.update_data(download_result=result, download_lang=lang, user_status=user_status)
        await state.set_state(DownloadStates.confirm_download)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=LOCALIZATION[lang]["confirm_yes"], callback_data="confirm_dl_yes"),
            InlineKeyboardButton(text=LOCALIZATION[lang]["confirm_no"], callback_data="confirm_dl_no")
        ]])
        await message.answer(LOCALIZATION[lang]["confirm_title"].format(count=total_count), reply_markup=keyboard, parse_mode="Markdown")
        return

    await start_actual_download(message, result, lang, user_status, user_id)
            
@router.callback_query(DownloadStates.confirm_download, F.data == "confirm_dl_no")
async def cancel_download_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("download_lang", "en")
    await state.clear()
    
    await callback.message.edit_text(LOCALIZATION[lang]["download_cancelled"], reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(DownloadStates.confirm_download, F.data == "confirm_dl_yes")
async def accept_download_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    result = data.get("download_result")
    lang = data.get("download_lang", "en")
    user_status = data.get("user_status", "user")
    
    await state.clear()
    await state.update_data(user_lang=lang)
    
    await callback.answer()
    await callback.message.delete()
    await start_actual_download(callback.message, result, lang, user_status, callback.from_user.id)