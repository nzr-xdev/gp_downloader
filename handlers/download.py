from aiogram import Router, F
from aiogram.types import FSInputFile, CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import os
import asyncio
from core.ssyd import URLParser, GPDownloader
from handlers.start import LOCALIZATION, get_back_keyboard
import config
from mutagen.id3 import ID3

class DownloadStates(StatesGroup):
    confirm_download = State()

router = Router()
parser = URLParser()
downloader = GPDownloader()

async def start_actual_download(message: Message, download_data: dict, lang: str):
    status_msg = await message.answer(text=LOCALIZATION[lang]["processing"], parse_mode="Markdown")
    
    try:
        for url, (platform, mediatype) in download_data.items():
            output_files = await asyncio.to_thread(downloader.process, url, platform, mediatype)
            
            for file_path in output_files:
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    
                    await status_msg.edit_text(
                        LOCALIZATION[lang]["uploading"].format(filename=filename),
                        parse_mode="Markdown"
                    )
                    
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
                        print(f"⚠️ Не удалось вытащить thumb для Телеги: {e}")
                    
                    await message.answer_audio(
                        audio=audio_file,
                        thumbnail=thumb_file
                    )
                    
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    if os.path.exists(thumb_path):
                        os.remove(thumb_path)
                        
        await status_msg.delete()
        
        menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=LOCALIZATION[lang]["main_menu"]["button"], 
                callback_data=f"main_menu_{lang}"
            )]
        ])
        success_text = LOCALIZATION[lang]["success_text"]
        await message.answer(success_text, reply_markup=menu_keyboard, parse_mode="Markdown")

    except Exception as e:
        print(f"💥 DOWNLOAD EXECUTION CRASHED: {e}")
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LOCALIZATION[lang]["back"], callback_data=f"main_menu_{lang}")]
        ])
        error_msg = LOCALIZATION[lang].get("error_msg", "An error occurred:")
        await message.answer(f"{error_msg}\n`{str(e)}`", reply_markup=back_keyboard, parse_mode="Markdown")


@router.message(F.text)
async def handle_download(message: Message, state: FSMContext):
    
    state_data = await state.get_data()
    saved_lang = state_data.get("user_lang")

    if saved_lang:
        lang = saved_lang
    else:
        user_lang = message.from_user.language_code
        lang = user_lang if user_lang in LOCALIZATION else "en"

    # Using link_preparer from ssyd.py as it handles link extraction internally
    try:
        result, total_count = parser.link_preparer(message.text)
    except Exception as e:
        print(f"❌ Parsing failed or no links found: {e}")
        await message.answer(LOCALIZATION[lang].get("error_unknown_command"), reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
        return
        
    max_songs_per_request = config.get_settings("max_songs_per_request", 30)
    if total_count > max_songs_per_request:
        await message.answer(
            LOCALIZATION[lang].get("error_too_many_songs").format(max_songs=max_songs_per_request), 
            reply_markup=get_back_keyboard(lang), parse_mode="Markdown"
        )
        return

    # Multi-track handling with FSM confirmation
    if total_count > 1:
        await state.update_data(download_result=result, download_lang=lang)
        await state.set_state(DownloadStates.confirm_download)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=LOCALIZATION[lang]["confirm_yes"], callback_data="confirm_dl_yes"),
                InlineKeyboardButton(text=LOCALIZATION[lang]["confirm_no"], callback_data="confirm_dl_no")
            ]
        ])
        
        await message.answer(
            LOCALIZATION[lang]["confirm_title"].format(count=total_count), 
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return

    # Single track handling
    await start_actual_download(message, result, lang)
            
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
    
    await state.clear()
    await state.update_data(user_lang=lang)
    
    await callback.answer()
    await callback.message.delete()
    await start_actual_download(callback.message, result, lang)