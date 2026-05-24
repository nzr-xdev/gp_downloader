import json, os
from pathlib import Path
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db_handler import db

router = Router()

def load_all_localizations():
    CURRENT_DIR = Path(__file__).resolve().parent
    with open(CURRENT_DIR / "lang_models.json", "r", encoding="utf-8") as f:
        return json.load(f)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW_PATH = os.path.join(BASE_DIR, "assets", "preview.png")
LOCALIZATION = load_all_localizations()

def get_main_menu_keyboard(lang: str):
    lang_text = LOCALIZATION[lang]["main_menu"]
    
    keyboard = [
        [InlineKeyboardButton(text=lang_text["about"], callback_data=f"about_{lang}")],
        [InlineKeyboardButton(text=lang_text["help"], callback_data=f"help_{lang}")],
        [InlineKeyboardButton(text=lang_text["lang_settings"], callback_data=f"lang_settings_{lang}")],
        [InlineKeyboardButton(text=lang_text["feedback"], callback_data=f"feedback_{lang}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_keyboard(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LOCALIZATION[lang]["back"], callback_data=f"main_menu_{lang}")]
    ])

def get_language_selection_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="English 🇬🇧", callback_data="set_lang_en"),
        InlineKeyboardButton(text="Українська 🇺🇦", callback_data="set_lang_uk"),
        InlineKeyboardButton(text="Español 🇪🇸", callback_data="set_lang_es")
    )
    builder.row(InlineKeyboardButton(text=LOCALIZATION[lang]["back"], callback_data=f"main_menu_{lang}"))
    
    return builder.as_markup()

@router.message(Command("start"))
async def start_command(message: Message):
    await db.register_user(message.from_user.id)
    user_lang = message.from_user.language_code
    default_language = user_lang if user_lang in LOCALIZATION else "en"
    preview_file = FSInputFile(path=PREVIEW_PATH)
    
    welcome_text = LOCALIZATION[default_language]["welcome"]
    btn_text = LOCALIZATION[default_language]["main_menu"]["button"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, callback_data=f"main_menu_{default_language}")]
    ])
    await message.answer_photo(photo=preview_file)
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data.startswith("main_menu_"))
async def main_menu_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[-1]
    
    text = LOCALIZATION[lang]["main_menu"]["text"]
    
    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(lang), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("about_"))
async def about_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[-1]
    await callback.message.edit_text(LOCALIZATION[lang]["about"]["text"], reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("help_"))
async def help_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[-1]
    await callback.message.edit_text(LOCALIZATION[lang]["help"]["text"], reply_markup=get_back_keyboard(lang), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("lang_settings_"))
async def lang_settings_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[-1]
    
    await callback.message.edit_text(
        LOCALIZATION[lang]["lang_settings"]["text"], 
        reply_markup=get_language_selection_keyboard(lang),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_lang_"))
async def set_language_callback(callback: CallbackQuery, state: FSMContext):
    new_lang = callback.data.split("_")[-1]
    
    await state.update_data(user_lang=new_lang)

    await callback.answer(LOCALIZATION[new_lang]["localization_change"], show_alert=True)
    
    text = LOCALIZATION[new_lang]["main_menu"]["text"]
    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(new_lang), parse_mode="Markdown")

@router.callback_query(F.data.startswith("feedback_"))
async def feedback_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[-1]

    text = LOCALIZATION[lang]["feedback"]["text"]
    await callback.message.edit_text(
        text, 
        reply_markup=get_back_keyboard(lang), 
        parse_mode="Markdown"
    )
    await callback.answer()





@router.message(F.text.startswith("/"))
async def unknown_command_handler(message: Message):
    user_lang = message.from_user.language_code
    lang = user_lang if user_lang in LOCALIZATION else "en"

    error_text = LOCALIZATION[lang].get("error_unknown_command")

    await message.answer(
        error_text, 
        reply_markup=get_main_menu_keyboard(lang), 
        parse_mode="Markdown"
    )