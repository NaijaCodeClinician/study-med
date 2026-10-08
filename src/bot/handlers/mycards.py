"""
This is file is the mycards command flow handler. It handles the viewing, editing and deleting of user created flashcards
"""

from aiogram import F, Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types.message import Message

from src.imports import MyCardState, subject_keyboard

router = Router()


# ========= MYCARDS COMMAND ENTRY POINT ===========
@router.message(Command("mycards"))
async def mycards_entry(message: Message, state: FSMContext):
    """
    The entry point handler of the mycards command
    """

    await state.clear()

    await state.set_state(MyCardState.subject)
    await message.answer(
        text="<b>✋Hi there!</b> Let's view your available flashcards\n\n"
        "<i>Pick a subject you'd like to view it's created flashcards</i>",
        reply_markup=subject_keyboard([]),
    )
