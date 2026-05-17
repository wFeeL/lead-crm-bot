from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.builders import MenuCallback, main_menu_keyboard
from app.bot.texts.user import FAQ_TEXT, START_TEXT, SUPPORT_TEXT

router = Router(name="user_start")


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(START_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(MenuCallback.filter(F.action == "back"))
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(START_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "support"))
async def support(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(SUPPORT_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(MenuCallback.filter(F.action == "faq"))
async def faq(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(FAQ_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message()
async def fallback(message: Message, session: AsyncSession) -> None:
    _ = session
    await message.answer(
        "Не получилось обработать действие. Вернитесь в главное меню.",
        reply_markup=main_menu_keyboard(),
    )
