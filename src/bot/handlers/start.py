"""
This is start flow handler, it handles the /start command, and every flow associated with it,
ranging from spanning over; subject selection, topics selection, and study reminder
"""

import asyncio

from aiogram import F
from aiogram.dispatcher.router import Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types.callback_query import CallbackQuery
from aiogram.types.message import Message

from src.imports import (
    StartBotState,
    weak_subjects_keyboard,
    weak_topics_keyboard,
)
from src.utils.helpers import (
    get_subject_id,
    get_subjects,
    get_topic_id,
    get_topics_id,
    minutes_to_24h,
)
from src.utils.loader import load_subjects_content
from src.utils.validators import validate_and_detect_format

router = Router()
subject_content = load_subjects_content()
available_subjects_dict = get_subjects(
    subject_content
)  # Get available subjects in subjects.json

available_subjects = [subject["name"] for subject in available_subjects_dict]

# ===================== START COMMAND HANDLER ===================


# ======== WEAK SUBJECTS SELECTION FLOW ========


@router.callback_query(
    StartBotState.subjects, F.data.startswith("weak_sub:")
)  # Handle topics selection
async def select_subjects(callback: CallbackQuery, state: FSMContext):
    """
    The callback query handler for subjects selection
    """
    data = await state.get_data()
    subject_id = callback.data.removeprefix(  # type:ignore
        "weak_sub:"
    )
    subject = get_subject_id(subject_content, subject_id)

    if (
        subject is None
    ):  # If the selected subject is not in the available subjects (safe fallback, not likely to occur)
        await callback.answer(
            "⛔ Invalid subject.",
            show_alert=True,
        )  # Send message as an alert
        return  # Exit, to not process any further

    selected_subjects = data.get(
        "subjects",
        [],
    )  # Get the selected subjects by the user

    # Check or uncheck a subject
    if any(
        sel_subject["id"] == subject_id for sel_subject in selected_subjects
    ):  # If a subject has already been selected before (user deselected / unchecked the subject)
        selected_subjects.remove(
            subject
        )  # Remove subject from the selected subjects list
    else:  # Subject has not been selected before
        selected_subjects.append(subject)  # Add subject to selected subjects list

    await state.update_data(
        subjects=selected_subjects
    )  # Update the FSM state data with the selected subjects

    await callback.answer()

    await callback.message.edit_reply_markup(  # type:ignore
        reply_markup=weak_subjects_keyboard(
            subjects=available_subjects_dict,
            selected_subjects=selected_subjects,
        )  # Render the topics inline keyboard
    )


@router.callback_query(
    StartBotState.subjects, F.data == "weak_sub_next"
)  # Handle the done button for the subjects
async def finish_subjects(callback: CallbackQuery, state: FSMContext):
    """
    The callback handler for the next button (for the multi choice inline keyboard)
    """

    data = await state.get_data()  # Get the temporary FSM data for the user

    selected_subjects = data.get("subjects", [])  # Get user selected subjects

    if not selected_subjects:  # If user didn't select any subject but still tapped Done
        await callback.answer(  # type:ignore
            "⛔ Select at least one subject first",
            show_alert=True,
        )  # Send this alert
        return  # Exit, do not proceed any further

    await state.set_state(
        StartBotState.topics
    )  # Move FSM state to the next (FSM knowledge state)
    current_index = 0

    await state.update_data(current_index=current_index)
    first_subject = selected_subjects[current_index]
    available_topics = get_topics_id(subject_content, first_subject["id"])

    if not available_topics:
        await callback.answer(
            f"⛔ No topics available for {first_subject}", show_alert=True
        )
        return

    await callback.answer()
    is_last = len(selected_subjects) == 1
    await callback.message.edit_text(  # type:ignore
        f"📚 <b>{first_subject['name']}</b>\n\n"
        "Select one or more topics.\n\n"
        "You must select at least one topic "
        "before continuing.",
        reply_markup=weak_topics_keyboard(
            available_topics,
            selected_topics=[],
            is_last=is_last,
        ),
    )


@router.callback_query(StartBotState.subjects, F.data == "weak_sub_skip")
async def skip_subjects(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(  # type:ignore
        "📢⚠ <b>NOTE:</b> Skipping overrides any previously inputted subject or topic\n\n"
        "⏩ Skipping weak subject and topic selection"
    )

    await asyncio.sleep(2)

    await state.set_state(StartBotState.study_time)

    await callback.message.edit_text(  # type:ignore
        "⏰ <b>When would you like StudyMed to remind you to study?</b>\n\n"
        "Choose a time that fits naturally into your day. <b>Sleep comes first, </b>"
        "so StudyMed only allows study reminders between <b>6:00 AM and 10:00 PM</b>\n\n"
        "Please enter your preferred time in <b>24-hour format or 12-hour format.</b>\n\n"
        "<b>Examples:</b> 07:00, 13:00, 7am, 01:00 AM\n\n"
    )


@router.message(
    StartBotState.subjects, F.entities
)  # Handle and block text messages during subject selection
async def subject_command_block(message: Message):
    """
    Text blocker for FSM subject state (user can only select subjects using the inline keyboard), and can't send commands
    """
    entities = message.entities or []
    has_command = any(entity.type == "bot_command" for entity in entities)

    if has_command:
        await message.reply(
            "⛔ You're currently selecting your subjects\n\n"
            "If you want to quit, kindly click ❌ Cancel"
        )
        return
    await message.reply(
        "⛔ Please choose your subject(s) using the buttons provided.\n\n"
        "When you're finished, press ▶ Next."
    )


@router.message(StartBotState.subjects)  # Fallback if the first block didn't work
async def subjects_text_blocked(message: Message):
    """
    Text blocker for FSM subject state (user can only select subjects using the inline keyboard)
    """
    await message.reply(
        "⛔ Please choose your subject(s) using the buttons provided.\n\n"
        "When you're finished, press ▶ Next."
    )


# ======== TOPICS SELECTION FLOW =========


@router.callback_query(StartBotState.topics, F.data.startswith("weak_topic:"))
async def select_topics(callback: CallbackQuery, state: FSMContext):
    """
    The callback query handler for weak topics selection
    """
    data = await state.get_data()
    topic_id = callback.data.removeprefix(  # type:ignore
        "weak_topic:"
    )
    topic = get_topic_id(subject_content, topic_id)

    if not topic:
        # If the selected topic is not in the available topics (safe fallback, not likely to occur)
        await callback.answer(
            "⛔ Invalid topic.",
            show_alert=True,
        )  # Send message as an alert
        return  # Exit, to not process any further

    user_selected_subjects = data.get("subjects")

    if not user_selected_subjects:
        await callback.answer(
            "⛔ Subject selection is empty, skipping to 📚study ⏰time setting",
            show_alert=True,
        )
        await state.set_state(StartBotState.study_time)
        await callback.message.edit_text(  # type:ignore
            "⏰"
        )
        return
    current_index = data.get("current_index", 0)
    current_subject = user_selected_subjects[current_index]

    is_last = current_index >= len(user_selected_subjects) - 1
    available_topics = get_topics_id(
        subject_content, current_subject["id"]
    )  # Get available topics for a selected subject

    if not any(
        av_topic["id"] == topic["id"] for av_topic in available_topics
    ):  # If the selected topic is not in the available topics (safe fallback, not likely to occur)
        await callback.answer(
            "⛔ Invalid topic.",
            show_alert=True,
        )  # Send message as an alert
        return  # Exit, to not process any further

    weak_subjects = data.get(
        "weak_subjects",
        {},
    )

    weak_subjects.setdefault(current_subject, [])

    selected_topics = weak_subjects.get(current_subject, [])

    # Check or uncheck a topic
    if any(
        sel_topic["id"] == topic["id"] for sel_topic in selected_topics
    ):  # If a topic has already been selected before (user deselected / unchecked the topic)
        selected_topics.remove(topic)  # Remove topic from the selected topics list
    else:  # Topic has not been selected before
        selected_topics.append(topic)  # Add topic to selected topics list

    weak_subjects[current_subject] = selected_topics

    await state.update_data(
        weak_subjects=weak_subjects
    )  # Update the FSM state data with the selected topics

    await callback.answer()

    await callback.message.edit_reply_markup(  # type:ignore
        reply_markup=weak_topics_keyboard(
            topics=available_topics, selected_topics=selected_topics, is_last=is_last
        )  # Render the topics inline keyboard
    )


@router.callback_query(StartBotState.topics, F.data == "weak_topic_next")
async def next_topic(callback: CallbackQuery, state: FSMContext):
    """
    The callback handler for the next button (for the multi choice inline keyboard)
    """

    data = await state.get_data()

    user_selected_subjects = data.get("subjects")
    if not user_selected_subjects:
        await callback.answer(
            "⛔ Subject selection is empty, skipping to 📚study ⏰time setting",
            show_alert=True,
        )
        await state.set_state(StartBotState.study_time)
        await callback.message.edit_text(  # type:ignore
            "⏰ <b>When would you like StudyMed to remind you to study?</b>\n\n"
            "Choose a time that fits naturally into your day. <b>Sleep comes first, </b>"
            "so StudyMed only allows study reminders between <b>6:00 AM and 10:00 PM</b>\n\n"
            "Please enter your preferred time in <b>24-hour format or 12-hour format.</b>\n\n"
            "<b>Examples:</b> 07:00, 13:00, 7am, 01:00 AM\n\n"
        )
        return

    current_index = data.get("current_index", 0)
    current_subject = user_selected_subjects[current_index]

    weak_subjects = data.get("weak_subjects", {})

    weak_topics = weak_subjects.get(current_subject, [])

    if not weak_topics:
        weak_subjects[current_subject] = []
        await state.update_data(weak_subjects=weak_subjects)

    next_index = current_index + 1

    if next_index >= len(user_selected_subjects) - 1:
        return

    next_subject = user_selected_subjects[next_index]

    next_available_topics = get_topics_id(
        subject_content, next_subject["id"]
    )  # Get available topics for a selected subject

    next_weak_topics = data.get("weak_subjects", {}).get(next_subject, [])

    is_last = next_index >= len(user_selected_subjects) - 1

    await state.update_data(current_index=next_index)

    await callback.answer()

    await callback.message.edit_text(  # type:ignore
        f"📚 <b>{next_subject['name']}</b>\n\n"
        "Select one or more topics.\n\n"
        "You must select at least one topic "
        "before continuing.",
        reply_markup=weak_topics_keyboard(
            topics=next_available_topics,
            selected_topics=next_weak_topics,
            is_last=is_last,
        ),
    )


@router.callback_query(StartBotState.topics, F.data == "weak_topic_back")
async def topic_back(callback: CallbackQuery, state: FSMContext):
    """
    The callback handler for the back button during topic selection
    """
    data = await state.get_data()

    current_index = data.get("current_index", 0)

    user_selected_subjects = data.get("subjects", [])

    if current_index == 0:
        await state.set_state(StartBotState.subjects)
        await callback.answer()
        await callback.edit_text(  # type:ignore
            text=f"✋Hi <b>{callback.from_user.full_name if callback.from_user.full_name else callback.from_user.username}</b>"  # type: ignore
            "\n<i>Let's continue with your setup.</i>\n\n<b>Select your weak subjects:</b>",
            reply_markup=weak_subjects_keyboard(
                subjects=available_subjects_dict,
                selected_subjects=user_selected_subjects,
            ),
        )
        return

    back_index = current_index - 1

    back_subject = user_selected_subjects[back_index]

    weak_subjects = data.get("weak_subjects", {})

    weak_topics = weak_subjects.get(back_subject, [])
    available_topics = get_topics_id(
        subject_content, back_subject["id"]
    )  # Get available topics for a selected subject

    await callback.answer()

    await callback.message.edit_text(  # type:ignore
        f"📚 <b>{back_subject['name']}</b>\n\n"
        "Select one or more topics then <b>▶ Next</b>.\n\n"
        "<i>Or only click</i> <b>▶ Next</b> <i>without selecting a topic, if undecided</i>",
        reply_markup=weak_topics_keyboard(
            topics=available_topics,
            selected_topics=weak_topics,
        ),
    )


@router.callback_query(StartBotState.topics, F.data == "weak_topic_finish")
async def finish_topics(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.edit_text(  # type:ignore
        "✅ Your weak subjects and topics have successfully been saved 💾\n"
        "🤚 Hold on while the changes are being processed..."
    )
    await asyncio.sleep(2)

    await state.set_state(StartBotState.study_time)
    await callback.edit_text(  # type:ignore
        "⏰ <b>When would you like StudyMed to remind you to study?</b>\n\n"
        "Choose a time that fits naturally into your day. <b>Sleep comes first, </b>"
        "so StudyMed only allows study reminders between <b>6:00 AM and 10:00 PM</b>\n\n"
        "Please enter your preferred time in <b>24-hour format or 12-hour format.</b>\n\n"
        "<b>Examples:</b> 07:00, 13:00, 7am, 01:00 AM\n\n"
    )


@router.message(
    StartBotState.topics, F.entities
)  # Handle and block text messages during topics selection
async def topics_command_block(message: Message):
    """
    Text blocker for FSM topics state (user can only select topics using the inline keyboard), and can't send commands
    """
    entities = message.entities or []
    has_command = any(entity.type == "bot_command" for entity in entities)

    if has_command:
        await message.reply(
            "⛔ You're currently selecting your topics\n\n"
            "If you want to quit, kindly click ❌ Cancel"
        )
        return
    await message.reply(
        "⛔ Please choose your topic(s) using the buttons provided.\n\n"
        "When you're finished, press ▶ Next."
    )


@router.message(StartBotState.topics)  # Fallback if the first block didn't work
async def topics_text_blocked(message: Message):
    """
    Text blocker for FSM subject state (user can only select subjects using the inline keyboard)
    """
    await message.reply(
        "⛔ Please choose your topic(s) using the buttons provided.\n\n"
        "When you're finished, press ▶ Next."
    )


@router.message(StartBotState.study_time)
async def set_study_time(message: Message, state: FSMContext):
    """
    User's study time handler
    """

    time_input = message.text if message.text else ""
    valid_time, time_format = validate_and_detect_format(time_input)

    if valid_time is None or time_format is None:  # Validate the inputted study time
        await message.reply("⛔ <b>Invalid ⌚time</b>\n\nPlease enter a valid ⌚time")
        return

    study_time = minutes_to_24h(valid_time)
    await state.update_data(study_time=study_time)
    await state.clear()

    await message.answer(
        "<b>✅ Profile has been setup successfully 👏</b>\n"
        f"<i>🤖StudyMed will be sending study reminders every day at {study_time}</i>\n\n"
        "<b>🙄❓What would you like to do now?</b>\n<i>📚 Available commands:</i>\n\n"
        '🧠 <a href="tg://bot_command?command=quiz">/quiz</a> — Take a quiz\n'
        '➕ <a href="tg://bot_command?command=add">/add</a> — Create a knowledge card\n'
        '🗃 <a href="tg://bot_command?command=mycards">/mycards</a> — View your cards\n'
        '📊 <a href="tg://bot_command?command=stats">/stats</a> — View your statistics\n'
    )


# ===================================================
# ==================== ENTRY POINT ==================
# ===================================================


@router.message(Command("start"))  # Start command handler
async def start_entry(message: Message, state: FSMContext):
    """
    The /start command entry point handler
    """

    await state.clear()  # Clear any existing states in the FSM

    await state.set_state(StartBotState.subjects)  # Set FSM state

    await message.answer(
        text=f"😊🎉 Welcome <b>{message.from_user.full_name if message.from_user.full_name else message.from_user.username}</b> "  # type: ignore
        "to <b>🧠🩺StudyMed</b> your personalized 📚Study Assistant.\n\n<i>Let's get you all setup.</i>\n\n<b>Select your weak subjects:</b>",
        reply_markup=weak_subjects_keyboard(
            subjects=available_subjects_dict, selected_subjects=[]
        ),
    )
