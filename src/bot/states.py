"""
This module is a collection of State Classes (FSM)
"""

from aiogram.fsm.state import State, StatesGroup


class AddCardState(StatesGroup):
    """
    The state class for the add knowledge card flow
    """

    subject = State()  # The subject state (user is selecting a subject)
    topics = State()  # The topics state (user is selecting topics)
    knowledge = State()  # The knowledge state (user is creating the knowledge card)
    generating = State()  # The generating state (AI is generating the question and answer from the created knowledge card)
    review = (
        State()
    )  # The review state (user is reviewing the generated question and answer)


class StartBotState(StatesGroup):
    """
    The state class for the start bot flow
    """

    subjects = State()  # The subject states (user is selecting subjects)
    topics = State()  # The topics state (user is selecting topics)
    study_time = (
        State()
    )  # The study time state (user is choosing his or her study time)


class QuizState(StatesGroup):
    """
    The state class for the quiz flow
    """

    location = State()  # Where the questions come from
    subject = State()  # If the selected location, allows it
    topics = State()  # If the selected location, allows it
    start = State()  # Quiz is ready / users starts
    review = State()  # Quiz in progress / answers are stored temporarily
    finish = State()  # User is done with quiz
