"""
This is file is the quiz command flow handler. It handles the quiz mode
"""

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types.message import Message

router = Router()


# ========= QUIZ COMMAND ENTRY POINT ===========
@router.message(Command("quiz"))
async def quiz_entry(message: Message):
    """
    The entry point handler of the quiz command
    """

    await message.reply(
        "👋Hi there! Welcome to StudyMed "
        "<b>Sorry, but this command is currently unavailable</b>\n"
        "You can only be creating Flashcards for now (/add)\n\n"
        "😔Sorry for any inconveniences, we hope that StudyMed improves your study skills\n"
        "<i>Keep growing</i>"
    )
