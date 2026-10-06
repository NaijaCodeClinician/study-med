"""
This module is a collection of all the various inline keyboards for different phases for the Telegram interface of StudyMed
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def subject_keyboard(
    subjects: list[dict], selected_subject: str = ""
) -> InlineKeyboardMarkup:
    """
    This is the subjects inline keyboard for the Telegram add flow
    """
    buttons = []
    sorted_subjects = sorted(subjects, key=lambda subject: subject["name"])
    for subject in sorted_subjects:
        emoji = "🔘" if selected_subject != subject["id"] else "🟢"
        text = f"{emoji}    {subject['icon']} {subject['name']}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"subject:{subject['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="subject_cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topics_keyboard(
    topics: list[dict],
    selected_topics: list[dict],
) -> InlineKeyboardMarkup:
    """
    This is the topics inline keyboard for the Telegram add flow
    """
    buttons = []
    sorted_topics = sorted(topics, key=lambda topic: topic["name"])
    for topic in sorted_topics:
        selected_emoji = (
            "🔘"
            if not any(topic["id"] == sel_topic["id"] for sel_topic in selected_topics)
            else "🟢"
        )
        text = f"{selected_emoji}   {topic['icon']} {topic['name']}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"topic:{topic['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="◀ Back",
                callback_data="topic_back",
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="topic_cancel",
            ),
        ],
    )
    buttons.append(
        [
            InlineKeyboardButton(
                text="✅ Done",
                callback_data="topic_done",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def review_keyboard(can_regenerate: bool = True) -> InlineKeyboardMarkup:
    """
    This is the knowledge review inline keyboard for the Telegram add flow
    """
    regenerate_button = []
    back_button = []

    if (
        can_regenerate
    ):  # If user can regenerate, add regenerate button to the inline keyboard
        regenerate_button.append(
            InlineKeyboardButton(text="🔁 Regenerate", callback_data="card_regenerate")
        )
        back_button.append(
            InlineKeyboardButton(text="◀ Back", callback_data="card_back")
        )

    inline_keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Save",
                callback_data="card_save",
            ),  # The Save button
            *regenerate_button,  # Optional Regenerate button if user can regenerate
        ],
        [
            *back_button,  # Optional back button if user can regenerate
            InlineKeyboardButton(text="❌ Cancel", callback_data="card_cancel"),
        ],  # The Cancel button, is in a different list, so that Telegram displays it below the Save and Regenerate buttons
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def knowledge_keyboard(retry=False):
    """
    The knowledge input inline keyboard
    """
    if retry:
        retry_button = InlineKeyboardButton(
            text="🔁 Retry", callback_data="knowledge_retry"
        )
    inline_keyboard = [
        [
            InlineKeyboardButton(
                text="◀ Back",
                callback_data="knowledge_back",
            ),
            *retry_button,
        ],
        [
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="knowledge_cancel",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def weak_subjects_keyboard(subjects: list[dict], selected_subjects: list[dict]):
    """
    The inline keyboard for weak subjects
    """

    buttons = []

    sorted_subjects = sorted(subjects, key=lambda subject: subject["name"])
    for subject in sorted_subjects:
        emoji = (
            "🔘"
            if not any(
                subject["id"] == sel_subject["id"] for sel_subject in selected_subjects
            )
            else "🟢"
        )
        text = f"{emoji}    {subject['icon']} {subject['name']}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"weak_sub:{subject['id']}")]
        )
    buttons.append(
        [
            InlineKeyboardButton(text="⏩ Skip", callback_data="weak_sub_skip"),
            InlineKeyboardButton(text="▶ Next", callback_data="weak_sub_next"),
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text="❌ Cancel", callback_data="weak_sub_cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def weak_topics_keyboard(
    topics: list[dict],
    selected_topics: list[dict],
    is_last=False,
):
    """
    The inline keyboard for weak topics
    """

    buttons = []

    sorted_topics = sorted(topics, key=lambda topic: topic["name"])
    for topic in sorted_topics:
        selected_emoji = (
            "🔘"
            if not any(topic["id"] == sel_topic["id"] for sel_topic in selected_topics)
            else "🟢"
        )
        text = f"{selected_emoji}   {topic['icon']} {topic['name']}"
        buttons.append(
            [InlineKeyboardButton(text=text, callback_data=f"weak_topic:{topic['id']}")]
        )
    continue_button = (
        InlineKeyboardButton(text="▶ Next", callback_data="weak_topic_next")
        if not is_last
        else InlineKeyboardButton(text="✅ Finish", callback_data="weak_topic_finish")
    )
    buttons.append(
        [
            InlineKeyboardButton(text="◀ Back", callback_data="weak_topic_back"),
            continue_button,
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text="❌ Cancel", callback_data="weak_topic_cancel")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def quiz_location_keyboard(selected_button: str):
    button_mapping = {
        "quiz_bank": "🗃 StudyMed question bank",
        "quiz_cards": "📚 Your Flashcards",
        "quiz_random": "🎲 Random",
    }
    buttons = [
        [InlineKeyboardButton(text="🎯 Recommended", callback_data="quiz_recommend")],
        [InlineKeyboardButton(text="📚 Question bank", callback_data="quiz_bank")],
        [InlineKeyboardButton(text="📂 My Flashcards", callback_data="quiz_cards")],
        [InlineKeyboardButton(text="🎲 Random", callback_data="quiz_random")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="quiz_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def study_time_keyboard():
    """
    Inline keyboard in the add handler, for the study time FSM state
    """

    buttons = [
        [
            InlineKeyboardButton(text="◀ Back", callback_data="time_back"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="time_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
