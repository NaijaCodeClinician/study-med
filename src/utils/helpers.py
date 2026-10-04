"""
A compilation of helper functions that aid StudyMed to perform little background objectives
"""

import re

# ==========================================
#       SUBJECTS.JSON FILE OPERATIONS
# ==========================================


def get_subjects(content: dict) -> list[dict]:
    """
    Get and return a list of subjects

    Args:
        content (dict): A dictionary containing the list of subjects to be retrieved

    Returns:
        list[dict]: The list of subjects (**dictionary**) to be returned
    """

    return content["subjects"]


def get_subject_id(content: dict, subject_id: str | int) -> dict | None:
    """
    Get a return a subject with that same **ID** as the search **subject_id**

    Args:
        content (dict): A dictionary containing a list of subjects

    Returns:
        dict | None: The subject (**dictionary**) to be returned, None if no match
    """

    try:
        subject_id = int(subject_id)
    except ValueError:
        raise ValueError("Invalid ID, search ID must be a number")

    for subject in content["subjects"]:
        if subject.get("id", "") == subject_id:
            return subject
    return None


def get_topics_id(content: dict, subject_id: str | int) -> list[dict]:
    """
    Get and return a list of topics belonging to a subject (using it's **subject ID**)

    Args:
        content (dict): A dictionary containing the list of subjects and that of topics
        subject_id (str | int): Search item (**ID**) of the subject, that will be used to retrieve it's topics

    Returns:
        list[dict]: The list of topics (**dictionary**) to be returned
    """

    topics = []

    try:
        subject_id = int(subject_id)
    except ValueError:
        raise ValueError("Invalid ID, search ID must be a number")

    for topic in content["topics"]:  # Loop through the topics in content
        if (
            topic.get("subject_id", "") == subject_id
        ):  # If a topic has the same subject_id as the search id, add to list
            topics.append(topic)
    return topics


def get_topic_id(content: dict, topic_id: str | int) -> dict | None:
    """
    Get a return a topic with that same **ID** as the search **topic_id**

    Args:
        content (dict): A dictionary containing a list of subjects and topics

    Returns:
        dict | None: The topic (**dictionary**) to be returned, None if no match
    """

    try:
        topic_id = int(topic_id)
    except ValueError:
        raise ValueError("Invalid ID, search ID must be a number")

    for topic in content["topics"]:
        if topic.get("id", "") == topic_id:
            return topic
    return None


# =========================================
#       TIME HELPERS
# =========================================


def convert_to_minutes(hour: int, minute: int, meridian: str | None) -> int | None:
    """Convert time to minutes since midnight."""
    if minute < 0 or minute > 59:
        return None

    if meridian:
        if hour < 1 or hour > 12:
            return None

        if meridian == "am":
            if hour == 12:
                hour = 0
        else:  # pm
            if hour != 12:
                hour += 12

    else:
        if hour < 0 or hour > 23:
            return None
    return hour * 60 + minute


def minutes_to_24h(minutes: int) -> str:
    """Convert minutes since midnight to 24-hour format."""
    hour = minutes // 60
    minute = minutes % 60
    return f"{hour:02d}:{minute:02d}"


def parse_time(time_str: str) -> int | None:
    """Parse a single time string to minutes since midnight."""
    time_str = time_str.strip().lower()
    pattern = r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$"
    match = re.match(pattern, time_str)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    meridian = match.group(3)
    return convert_to_minutes(hour, minute, meridian)
