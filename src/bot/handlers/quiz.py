from aiogram import F, Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types.message import Message

router = Router()


@router.message(Command("quiz"))
async def quiz_handler(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(text="")
