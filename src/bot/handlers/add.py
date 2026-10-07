"""
This is add flow handler, it handles the /add command, and every flow associated with it,
ranging from spanning over; subject selection, topics selection, knowledge inputting and knowledge card reviewing
"""

from aiogram import F, Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types.callback_query import CallbackQuery
from aiogram.types.message import Message

from src.imports import (
    AddCardState,
    KnowledgeCard,
    configs,
    knowledge_keyboard,
    review_keyboard,
    subject_keyboard,
    topics_keyboard,
)
from src.services.ai import StudyMedAI
from src.storage.database import Database
from src.storage.knowledge_card_store import KnowledgeCardStore
from src.utils.helpers import get_subject_id, get_subjects, get_topic_id, get_topics_id
from src.utils.loader import load_subjects_content

router = Router()  # Telegram's router
database = Database()
card_store = KnowledgeCardStore(database)
study_med_ai = StudyMedAI()
subject_content = load_subjects_content()
available_subjects_dict = get_subjects(
    subject_content
)  # Get available subjects in subjects.json

available_subjects = [subject["name"] for subject in available_subjects_dict]

MAX_REGENERATIONS = int(
    configs.get("ai", {}).get("max_regenerations", 3)
)  # Maximum regeneration limit

# ============================================ ADD COMMAND HANDLER ============================================ #

# ====== SUBJECT SELECTION FLOW ====== #


@router.callback_query(
    AddCardState.subject, F.data.startswith("subject:")
)  # Handler after the user has selected a subject
async def select_subject(callback: CallbackQuery, state: FSMContext):
    """
    The callback query handler for subjects (when the user chooses a subject)
    """

    subject_id = callback.data.removeprefix(  # type: ignore
        "subject:"
    )
    subject = get_subject_id(subject_content, subject_id)

    if subject is None:
        # If user by chance selects a non-existing subject (a safe fallback, not likely to happen)
        await callback.answer(
            "⛔ Invalid subject.",
            show_alert=True,
        )  # Send message as an alert (notification) not normal Telegram message
        return  # Exit, do not process any further for this case

    await state.update_data(
        subject=subject,
        topics=[],
    )  # Update the FSM state with the selected subject (for temporary storage)

    await callback.message.edit_reply_markup(  # type:ignore
        reply_markup=subject_keyboard(
            available_subjects_dict, selected_subject=subject["id"]
        )  # Show that subject has been selected
    )
    await state.set_state(AddCardState.topics)  # Move to next FSM state (topics state)

    topics = get_topics_id(
        subject_content, subject_id
    )  # Get the topics for particular subject

    await callback.answer()

    await callback.message.edit_text(  # type:ignore
        f"📚 <b>{subject['name']}</b>\n\n"
        "Select one or more topics.\n\n"
        "You must select at least one topic "
        "before continuing.",
        reply_markup=topics_keyboard(topics, selected_topics=[]),
    )  # Send the topics selection inline keyboard


@router.callback_query(
    AddCardState.subject, F.data == "subject_cancel"
)  # Handle the cancel callback
async def subject_cancel(callback: CallbackQuery, state: FSMContext):
    """
    Handles the ❌ Cancel callback query during subject selection
    """

    await state.clear()  # Clear all states (FSM)

    await callback.answer()  # Answer the user

    await callback.message.edit_text(  # type:ignore
        "❌ Subject selection and flashcard creation cancelled."
    )  # type:ignore # Edit the existing inline-keyboard and show flashcard cancelled to the user


@router.message(
    AddCardState.subject, F.entities
)  # Handle and block text messages during review
async def subject_command_block(message: Message):
    """
    Text blocker for FSM subject state (user can only select a subject using the inline keyboard and cannot send a command)
    """
    entities = message.entities or []
    has_command = any(entity.type == "bot_command" for entity in entities)

    if has_command:
        await message.answer(
            "⛔ You're currently selecting a subject\n\n"
            "If you want to quit, kindly click ❌ Cancel"
        )
        return
    await message.answer("⛔ Please choose a subject using the inline keyboard")


@router.message(AddCardState.subject)  # Fallback if the first block didn't work
async def subject_text_blocked(message: Message):
    """
    Text blocker for FSM subject state (user can only select a subject using the inline keyboard)
    """
    await message.answer(
        "⛔ Please choose a subject using the inline keyboard"
    )  # Send the not allowed message


# ====== TOPICS SELECTION FLOW ======


@router.callback_query(
    AddCardState.topics, F.data.startswith("topic:")
)  # Handle topics selection
async def select_topic(callback: CallbackQuery, state: FSMContext):
    """
    The callback query handler for topics selection
    """

    data = await state.get_data()  # Get user's temporary FSM data

    subject = data.get("subject")  # Get user selected subject

    if not subject:  # A safe fallback if user somehow bypasses subject selection
        await callback.answer(
            "⛔ Your subject selection is missing.\n\nPlease try again with /add",
            show_alert=True,
        )  # Send message as alert
        await callback.message.edit_reply_markup(reply_markup=None)  # type:ignore
        await state.clear()  # Clear existing FSM states
        return  # Exit, do not process any further for this case

    topic_id = callback.data.removeprefix(  # type:ignore
        "topic:"
    )

    topic = get_topic_id(subject_content, topic_id)
    if topic is None:
        # If the selected topic is not among the available topics (safe fallback, not likely to occur)
        await callback.answer(
            "⛔ Invalid topic.",
            show_alert=True,
        )  # Send message as an alert

        return  # Exit, to not process any further

    available_topics = get_topics_id(
        subject_content, subject["id"]
    )  # Get available topics for a selected subject

    selected_topics = data.get(
        "topics",
        [],
    )  # Get the selected topics by the user

    # Check or uncheck a topic
    if any(
        sel_topic["id"] == topic["id"] for sel_topic in selected_topics
    ):  # If a topic has already been selected before (user deselected / unchecked the topic)
        selected_topics.remove(topic)  # Remove topic from the selected topics list
    else:  # Topic has not been selected before
        selected_topics.append(topic)  # Add topic to selected topics list

    await state.update_data(
        topics=selected_topics
    )  # Update the FSM state data with the selected topics

    await callback.answer()

    await callback.message.edit_reply_markup(  # type:ignore
        reply_markup=topics_keyboard(
            topics=available_topics,
            selected_topics=selected_topics,
        )  # Render the topics inline keyboard
    )


@router.callback_query(
    AddCardState.topics, F.data == "topic_back"
)  # Back button (callback) handler
async def back_subjects(callback: CallbackQuery, state: FSMContext):
    """
    The callback query handler for the back button in the FSM topics state
    """

    await state.set_state(
        AddCardState.subject
    )  # Move FSM state back to the FSM subject state

    data = await state.get_data()
    current_subject = data.get("subject")

    if not current_subject:
        await callback.answer(
            "⛔ Subject selection not found, please start afresh", show_alert=True
        )
        return

    await callback.answer()

    await callback.edit_text(  # type: ignore
        "📚 <b>Choose a subject</b>\n\nSelect the subject for your knowledge card:",
        reply_markup=subject_keyboard(
            subjects=available_subjects_dict,
            selected_subject=current_subject["id"],
        ),  # Resend the subject selection inline keyboard,
    )


@router.callback_query(
    AddCardState.topics, F.data == "topic_done"
)  # Handle the done button for the topics inline keyboard
async def finish_topics(callback: CallbackQuery, state: FSMContext):
    """
    The callback handler for the done button (for the topics inline keyboard)
    """

    data = await state.get_data()  # Get the temporary FSM data for the user

    selected_topics = data.get("topics", [])  # Get user selected topics

    if not selected_topics:  # If user didn't select any topic but still tapped Done
        await callback.answer(  # type:ignore
            "❌ Select at least one topic first",
            show_alert=True,
        )  # Send this alert
        return  # Exit, do not proceed any further

    await state.set_state(
        AddCardState.knowledge
    )  # Move FSM state to the next (FSM knowledge state)

    await callback.answer()

    await callback.message.edit_text(  # type:ignore
        "📝 <b>Enter your knowledge</b>\n\n"
        "Send the medical knowledge you want "
        "StudyMed to turn into a flashcard\n\n"
        "💁‍♂️ Example:\n"
        "<i>The brachial plexus is formed by "
        "the anterior rami of C5-T1 spinal nerves.</i>",
        reply_markup=knowledge_keyboard(),
    )  # Send the follow-up message for the knowledge card item


@router.callback_query(
    AddCardState.topics, F.data == "topic_cancel"
)  # Handles the cancel callback during topic selection
async def topics_cancel(callback: CallbackQuery, state: FSMContext):
    """
    Handles the callback query for ❌ Cancel during topics selection
    """

    await state.clear()  # Clear all states (FSM)

    await callback.answer()  # Answer the user

    await callback.message.edit_text(  # type:ignore
        "❌ Topics selection and flashcard creation cancelled."
    )  # type:ignore # Edit the existing inline-keyboard and show flashcard cancelled to the user


@router.message(
    AddCardState.topics, F.entities
)  # Handle and block text messages during topic selection
async def topics_command_block(message: Message):
    """
    Text blocker for FSM topic state (user can only select topics using the inline keyboard), and can't send commands
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
        "When you're finished, press ✅ Done."
    )


@router.message(AddCardState.topics)  # Fallback if the first block didn't work
async def topics_text_blocked(message: Message):
    """
    Text blocker for FSM topic state (user can only select topics using the inline keyboard)
    """
    await message.reply(
        "⛔ Please choose your topic(s) using the buttons provided.\n\n"
        "When you're finished, press ✅ Done."
    )


# ====== KNOWLEDGE INPUT FLOW ======


@router.message(
    AddCardState.knowledge, F.entities
)  # Handle and block text messages during review
async def knowledge_command_block(message: Message):
    """
    Text blocker for FSM topic state (user can only select topics using the inline keyboard), and can't send commands
    """
    entities = message.entities or []
    has_command = any(entity.type == "bot_command" for entity in entities)

    if has_command:
        await message.reply(
            "⛔ You're currently adding a flashcard.\n"
            "Please enter the medical knowledge "
            "for the card\n\n"
            "If you want to quit, kindly click ❌ Cancel"
        )
        return


@router.message(AddCardState.knowledge)
async def receive_knowledge(message: Message, state: FSMContext):
    """
    The add flow handler (knowledge card router)
    """
    data = await state.get_data()

    subject = data.get("subject", "")
    subject_name = subject["name"]
    topics = data.get("topics", [])
    topics_name = [topic["name"] for topic in topics]
    knowledge = (
        message.text or ""
    ).strip()  # Convert knowledge to string  # type: ignore

    if not knowledge:  # If user sent an empty message
        await message.reply(
            "🙏 Please provide the knowledge you want to turn into a 🔖flashcard",
        )
        return

    await state.update_data(source_knowledge=knowledge, regeneration_count=0)
    await state.set_state(AddCardState.generating)  # Set FSM state to generating
    await message.reply(
        "🧠 Generating your flashcard...\n\nPlease wait."
    )  # Send generating indicator to user

    try:  # Try generating flashcard from the user's knowledge
        result = await study_med_ai.generate_flashcard(
            knowledge=knowledge, subject=subject_name, topics=topics_name
        )
        if result.status == "rejected":
            await state.set_state(AddCardState.knowledge)
            await message.reply(
                f"{result.reason}\nPlease check and resend your 🧠knowledge, <b>OR</b> use any of the buttons below",
                reply_markup=knowledge_keyboard(),
            )
            return

    except ValueError as error:  # If an error occurred during flashcard generation # noqa: BLE001
        await state.set_state(
            AddCardState.knowledge
        )  # Set state back to the former FSM's state (knowledge)
        await message.answer(
            f"{error}\n\n"
            "<b>Your source knowledge is stored temporarily on the system.</b>\n"
            "Your can either; <b>✍Type</b> and send the knowledge, <b>Click</b> 🔃 Retry to retry generation\n"
            "OR use any of the buttons below 👇",
            reply_markup=knowledge_keyboard(retry=True),
        )
        return

    await state.update_data(
        question=result.question,
        answer=result.answer,
        difficulty=result.difficulty,
        case_sensitive=result.case_sensitive,
        question_type=result.question_type,
        multi_choices=result.multi_choices,
    )

    await state.set_state(
        AddCardState.review
    )  # Set FSM's state to review (user is reviewing the generated flashcard)
    await message.reply(
        f"❓ <b>Question</b>\n{result.question}\n\n"
        f"✅ <b>Answer</b>\n{result.answer}\n\n"
        f"🎚 <b>Difficulty:</b>{result.difficulty}",
        reply_markup=review_keyboard(),  # User to reply using the customized review inline-keyboard
    )


@router.callback_query(
    AddCardState.knowledge, F.data == "knowledge_cancel"
)  # Handle the callback query if user clicks cancel during knowledge input
async def knowledge_cancel(callback: CallbackQuery, state: FSMContext):
    """
    Handles the callback query for ❌ Cancel during knowledge input
    """

    await state.clear()  # Clear all states (FSM)

    await callback.answer()  # Answer the user

    await callback.message.edit_text(  # type:ignore
        "❌ Knowledge input and flashcard creation cancelled.\nYou can send /add to start over again"
    )  # Edit the existing inline-keyboard and show flashcard cancelled to the user


@router.callback_query(
    AddCardState.knowledge, F.data == "knowledge_back"
)  # Handle the callback when user clicks back during knowledge input
async def knowledge_back(callback: CallbackQuery, state: FSMContext):
    """
    Handles the callback query for ◀ Back during knowledge input
    """

    data = await state.get_data()  # Get user's temporary FSM data

    subject = data.get("subject")  # Get user selected subject

    selected_topics = data.get("topics", [])

    if not subject:  # A safe fallback if user somehow bypasses subject selection
        await callback.answer(
            "⛔ Your subject selection is missing.\n\nPlease start from the beginning with /add"
        )  # Send message as alert
        await callback.message.edit_reply_markup(reply_markup=None)  # type:ignore
        await state.clear()  # Clear existing FSM states
        return  # Exit, do not process any further for this case

    if not available_subjects:  # A safe fallback if subject.json is empty
        await callback.answer(
            "❌ No subjects available.\n\nPlease try again later with /add",
        )
        await callback.message.edit_reply_markup(reply_markup=None)  # type:ignore
        await state.clear()
        return

    await state.set_state(AddCardState.topics)  # Move to next FSM state (topics state)

    topics = get_topics_id(
        subject_content, subject["id"]
    )  # Get the topics for particular subject

    if not topics:
        await callback.answer(
            f"❌ No topics available yet for {subject['name']}\n\n.Please try again with /add",
        )
        await callback.message.edit_reply_markup(reply_markup=None)  # type:ignore
        await state.clear()
        return

    await callback.answer()

    await callback.message.edit_text(  # type:ignore
        f"📚 <b>{subject['name']}</b>\n\n"
        "Select one or more topics.\n\n"
        "You must select at least one topic "
        "before continuing.",
        reply_markup=topics_keyboard(
            topics,
            selected_topics=selected_topics,
        ),
    )  # Send the topics selection inline keyboard


@router.callback_query(AddCardState.knowledge, F.data == "knowledge_retry")
async def knowledge_retry(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    source_knowledge = data.get("source_knowledge", "")
    subject = data.get("subject", "")
    topics = data.get("topics", [])
    topics_name = [topic["name"] for topic in topics]

    await state.set_state(AddCardState.generating)  # Set FSM state to generating
    await callback.answer(
        "🧠 Retrying flashcard generation...\n\nPlease wait."
    )  # Send generating indicator to user

    try:  # Try generating flashcard from the user's knowledge
        result = await study_med_ai.generate_flashcard(
            knowledge=source_knowledge, subject=subject["name"], topics=topics_name
        )

        if result.status == "rejected":
            await state.set_state(AddCardState.knowledge)
            await callback.message.edit_text(  # type:ignore
                f"{result.reason}\nPlease check and resend your 🧠knowledge, <b>OR</b> use any of the buttons below",
                reply_markup=knowledge_keyboard(),
            )
            return

    except ValueError as error:  # If an error occurred during flashcard generation # noqa: BLE001
        await state.set_state(
            AddCardState.knowledge
        )  # Set state back to the former FSM's state (knowledge)
        await callback.message.edit_text(  # type:ignore
            f"{error}\n\n"
            "<b>Your source knowledge is stored temporarily on the system.</b>\n"
            "Your can either; <b>✍Type</b> and send the knowledge, <b>Click</b> 🔃 Retry to retry generation\n"
            "OR use any of the buttons below 👇",
            reply_markup=knowledge_keyboard(retry=True),
        )
        return

    await state.update_data(
        question=result.question,
        answer=result.answer,
        difficulty=result.difficulty,
        case_sensitive=result.case_sensitive,
        question_type=result.question_type,
        multi_choices=result.multi_choices,
    )

    await state.set_state(
        AddCardState.review
    )  # Set FSM's state to review (user is reviewing the generated flashcard)
    await callback.message.edit_text(  # type:ignore
        f"❓ <b>Question</b>\n{result.question}\n\n"
        f"✅ <b>Answer</b>\n{result.answer}\n\n"
        f"🎚 <b>Difficulty:</b>{result.difficulty}",
        reply_markup=review_keyboard(),  # User to reply using the customized review inline-keyboard
    )


# =========== REVIEW CARD FLOW =========


@router.callback_query(
    AddCardState.review, F.data == "card_save"
)  # Handle the save button callback
async def save_card(callback: CallbackQuery, state: FSMContext):
    """
    Handles the callback when user clicks ✅ Save
    """

    data = await state.get_data()  # Get the temporary flashcard data
    try:  # Save the knowledge card into the database
        card = KnowledgeCard(
            subject=data["subject"],
            topics=data["topics"],
            source_knowledge=data["source_knowledge"],
            question=data["question"],
            answer=data["answer"],
            difficulty=data["difficulty"],
            case_sensitive=data["case_sensitive"],
        )
        card_store.save_card(user_id=callback.from_user.id, card=card)

    except Exception:  # noqa: BLE001
        await callback.answer(
            "❌ Failed to save the flashcard, try ✅ Save again", show_alert=True
        )
        return

    await state.clear()  # Clear all states (FSM)

    await callback.answer()  # Answer the user

    await callback.message.edit_text("✅ Flashcard saved successfully")  # type: ignore  # Edit the existing inline-keyboard and show flashcard saved to the user


@router.callback_query(
    AddCardState.review, F.data == "card_regenerate"
)  # Handle the regenerate button call back
async def regenerate_card(callback: CallbackQuery, state: FSMContext):
    """
    Handles the callback when user clicks 🔁 Regenerate
    """

    data = await state.get_data()  # Get the temporary flashcard data

    subject = data.get("subject", "")
    topics = data.get("topics", [])

    regeneration_count = data.get("regeneration_count", 0)  # Get regeneration count

    # Check if user has used up the number of regeneration
    await callback.answer()
    if regeneration_count >= MAX_REGENERATIONS:
        await callback.message.edit_text(  # type: ignore
            "⚠ You have reached the maximum number "
            "of regenerations for this flashcard.\n\n"
            "You can either save or cancel the current card.",
            reply_markup=review_keyboard(can_regenerate=False),
        )

        return

    # User has not exceeded regeneration limit
    knowledge = data["source_knowledge"]  # Access the source knowledge

    if not knowledge:
        await callback.message.edit_text(  # type: ignore
            "❌ The original knowledge for this card could not be found"
        )
        return

    # Get old Knowledge card info (as a fallback)
    old_question = data.get("question")
    old_answer = data.get("answer")
    old_difficulty = data.get("difficulty")
    old_case_sensitive = data.get("case_sensitive")
    old_question_type = data.get("question_type")
    old_multi_choices = data.get("multi_choices")

    await state.set_state(AddCardState.generating)
    await callback.message.edit_text("🔁 Regenerating your flashcard...\n\nPlease wait")  # type:ignore # Send the regeneration indicator

    try:  # Try regenerating the flashcard
        result = await study_med_ai.generate_flashcard(
            knowledge=knowledge,
            subject=subject,
            topics=topics,
        )
        if result.status == "rejected":
            await state.set_state(AddCardState.knowledge)
            await callback.message.edit_text(  # type:ignore
                f"{result.reason}\nPlease check and resend your 🧠knowledge, <b>OR</b> use any of the buttons below",
                reply_markup=knowledge_keyboard(),
            )
            return

    except ValueError as error:  # noqa: BLE001 # Generation failed, so return the user to review
        await state.set_state(AddCardState.review)  # Set state back to the review
        await state.update_data(
            question=old_question,
            answer=old_answer,
            difficulty=old_difficulty,
            case_sensitive=old_case_sensitive,
            question_type=old_question_type,
            multi_choices=old_multi_choices,
        )  # Update FSM state data to old Knowledge card info
        await callback.message.edit_text(  # type: ignore
            f"{error}",
            reply_markup=review_keyboard(
                can_regenerate=regeneration_count < MAX_REGENERATIONS
            ),
        )  # Send couldn't regenerate message
        await callback.answer("⛔ Regeneration failed", show_alert=True)
        return

    # Regeneration was successful
    regeneration_count += 1  # Increment the regeneration count
    await state.update_data(
        question=result.question,
        answer=result.answer,
        difficulty=result.difficulty,
        case_sensitive=result.case_sensitive,
        question_type=result.question_type,
        multi_choices=result.multi_choices,
        regeneration_count=regeneration_count,
    )

    await state.set_state(
        AddCardState.review
    )  # Set FSM's state to review (user is reviewing the generated flashcard)

    can_regenerate = regeneration_count < MAX_REGENERATIONS

    # Display the new flashcard

    limit_message = (
        "\n\n⚠ You have used all regenerations for this card."
        if not can_regenerate
        else ""
    )
    await callback.message.edit_text(  # type: ignore
        f"❓ <b>Question</b>\n{result.question}\n\n"
        f"✅ <b>Answer</b>\n{result.answer}\n\n"
        f"🎚 <b> Difficulty:</b>{result.difficulty}",
        f"{limit_message}",
        reply_markup=review_keyboard(can_regenerate=can_regenerate),
    )  # User to reply using the customized review inline-keyboard


@router.callback_query(
    AddCardState.review, F.data == "card_cancel"
)  # Handle the cancel button callback
async def cancel_card(callback: CallbackQuery, state: FSMContext):
    """
    Handles the callback when user clicks ❌ Cancel during card review
    """
    await callback.answer()  # Answer the user

    await state.clear()  # Clear all states (FSM)

    await callback.message.edit_text("❌ Flashcard creation cancelled.")  # type:ignore # Edit the existing inline-keyboard and show flashcard cancelled to the user


@router.callback_query(AddCardState.review, F.data == "card_back")
async def back_knowledge(callback: CallbackQuery, state: FSMContext):
    """
    Handles the callback when user clicks ◀ Back
    """

    await state.set_state(AddCardState.knowledge)

    await callback.answer()

    await callback.message.edit_text(  # type:ignore
        "📝 <b>Enter your knowledge</b>\n\n"
        "Send the medical knowledge you want "
        "StudyMed to turn into a flashcard\n\n"
        "💁‍♂️ Example:\n"
        "<i>The brachial plexus is formed by "
        "the anterior rami of C5-T1 spinal nerves.</i>",
        reply_markup=knowledge_keyboard(),
    )


@router.message(
    AddCardState.review, F.entities
)  # Handle and block text messages during review
async def review_command_block(message: Message, state: FSMContext):
    """
    Text blocker for FSM review state (user can only click the buttons on the inline keyboard), and can't send commands
    """
    entities = message.entities or []
    has_command = any(entity.type == "bot_command" for entity in entities)

    if has_command:
        data = await state.get_data()  # Get the temporary flashcard data

        regeneration_count = data.get("regeneration_count", 0)  # Get regeneration count

        can_regenerate = MAX_REGENERATIONS > regeneration_count
        extra = ", 🔁 Regenerate, ◀ Back" if can_regenerate else ""
        await message.reply(
            "⛔ You're currently reviewing a flashcard\n\n"
            f"Please use ✅ Save{extra} or ❌ Cancel.",
        )
        return
    await message.reply("⛔ Please use the buttons above to continue")


@router.message(
    AddCardState.review
)  # Handle and block text messages during review, fallback if the first block doesn't work
async def review_text_blocked(message: Message, state: FSMContext):
    """
    Text blocker for FSM review state (user can only click a button on the inline keyboard)
    """
    data = await state.get_data()  # Get the temporary flashcard data

    regeneration_count = data.get("regeneration_count", 0)  # Get regeneration count

    can_regenerate = MAX_REGENERATIONS > regeneration_count
    extra = ", 🔁 Regenerate, ◀ Back" if can_regenerate else ""
    await message.reply(
        f"Please use the buttons below to continue.\n\nChoose ✅ Save{extra} or ❌ Cancel.",
    )


# ========== ENTRY POINT FOR ADD ==========


@router.message(
    Command("add")
)  # Handle the /add command, it is at the bottom of the file, so that the command blocker can run (if user is already in an active add session)
async def add_entry(message: Message, state: FSMContext):
    """
    The entry point of the add flow
    """

    if not available_subjects:  # If subjects.json is empty
        await message.answer("❌ No subjects are currently available.")
        return  # Exit, do not process any further for this case

    await state.clear()  # Clear any existing states

    await state.set_state(
        AddCardState.subject
    )  # Set the FSM state to subject (user to pick or choose a subject)

    await message.answer(
        "📚 <b>Choose a subject</b>\n\nSelect the subject for your knowledge card:",
        reply_markup=subject_keyboard(
            available_subjects_dict
        ),  # Send the reply inline keyboard,
    )
