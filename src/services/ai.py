"""
This is the AI service for StudyMed.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from src.imports import configs

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AI_CONFIG = configs.get("ai", {})
AI_PROVIDER = AI_CONFIG.get("provider", "groq")

if not AI_PROVIDER:
    raise ValueError(
        "AI_CONFIG_ERROR: No AI provider is configured. "
        "Set the provider to either 'groq' or 'openai'."
    )


@dataclass
class GeneratedFlashCard:
    status: str
    question: str
    answer: str
    multi_choices: list[str]
    difficulty: str
    question_type: str
    case_sensitive: bool
    reason: str
    reason_code: str | None


class AIService:
    """Parent/base class for AI-powered StudyMed services."""

    def __init__(self):
        self.provider = str(AI_PROVIDER).strip().lower()

        if self.provider == "groq":
            self.api_key = os.getenv("GROQ_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "AI_CONFIG_ERROR: StudyMed's Groq API key is not configured."
                )

            self.client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.api_key,
            )
            self.model = AI_CONFIG.get("models", {}).get("groq", "openai/gpt-oss-20b")

        elif self.provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "AI_CONFIG_ERROR: StudyMed's OpenAI API key is not configured."
                )

            self.client = AsyncOpenAI(api_key=self.api_key)
            self.model = AI_CONFIG.get("models", {}).get("openai", "gpt-4o-mini")

        else:
            raise ValueError(
                "AI_CONFIG_ERROR: StudyMed currently supports only "
                "'groq' or 'openai' as the AI provider."
            )

        try:
            self.temperature = float(AI_CONFIG.get("temperature", 0.2))
            self.max_completion_tokens = int(
                AI_CONFIG.get("max_completion_tokens", 500)
            )
        except (TypeError, ValueError):
            raise ValueError(
                "AI_CONFIG_ERROR: The AI temperature or "
                "max_completion_tokens setting is invalid."
            ) from None

        if self.max_completion_tokens <= 0:
            raise ValueError(
                "AI_CONFIG_ERROR: max_completion_tokens must be greater than zero."
            )


class StudyMedAI(AIService):
    """AI service specifically for StudyMed."""

    def __init__(self):
        super().__init__()

    async def generate_flashcard(
        self, knowledge: str, subject: str, topics: list[str]
    ) -> GeneratedFlashCard:
        """Generate a flashcard from the student's submitted knowledge."""

        # Validate input before spending an API request.
        if not isinstance(knowledge, str) or not knowledge.strip():
            raise ValueError(
                "AI_INPUT_ERROR: Please provide some medical knowledge "
                "before generating a flashcard."
            )

        if not isinstance(subject, str) or not subject.strip():
            raise ValueError(
                "AI_INPUT_ERROR: No subject was provided for the flashcard."
            )

        if not isinstance(topics, list) or not topics:
            raise ValueError(
                "AI_INPUT_ERROR: Please select at least one topic for the flashcard."
            )

        if not all(isinstance(topic, str) and topic.strip() for topic in topics):
            raise ValueError("AI_INPUT_ERROR: One or more selected topics are invalid.")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """
You are StudyMed's medical flashcard generation engine.

Transform the student's submitted knowledge into ONE reliable study flashcard.

Rules:
- Use ONLY information supported by the submitted knowledge, subject, and topics.
- Never invent missing facts to make a card work.
- Never silently fill important gaps.
- If the knowledge is too vague, incomplete, non-medical, unsafe,
  contradictory, or otherwise unsuitable for a reliable flashcard, REJECT it.
- If the user provided input is a question (even if medical related), instead of a statement of medical fact, REJECT it.
- If medically accurate knowledge does not match the provided subject and/or topics, REJECT it.
- Set status to success if generation succeeds, otherwise rejected.
- Never return an empty response.
- A rejection reason will be shown directly to the student, so make it concise,
  friendly, and actionable.
- Difficulty must be exactly one of: easy, medium or difficult.
- case_sensitive determines whether capitalization must match when grading.
- question_type must be multiple_choice, short_answer, or long_answer.
- Do not mention prompts, APIs, schemas, token limits, or hidden instructions.
- Return JSON matching the supplied schema.

Rejection codes:
TOO_VAGUE, INSUFFICIENT_INFORMATION, NOT_MEDICAL,
UNSAFE_CONTENT, CONTRADICTORY_INFORMATION, NOT_STUDYABLE, DOESN'T_MATCH, OTHER.

Question-type rules:
multiple_choice:
- Create one focused question.
- Exactly 4 plausible options.
- Exactly ONE correct option.
- No all of the above or none of the above.
- Do not make the correct option obvious by length or wording.

short_answer:
- Create one focused question answerable in a few words or a short sentence.
- options must be an empty array.

long_answer:
- Create one focused explanatory question.
- The model answer may contain several sentences or structured points.
- options must be an empty array.
""",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Subject: {subject.strip()}\n"
                            f"Topics: {', '.join(topic.strip() for topic in topics)}\n"
                            f"Knowledge: {knowledge.strip()}"
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "generated_flashcard",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {
                                    "type": "string",
                                    "enum": ["success", "rejected"],
                                },
                                "question": {"type": "string"},
                                "answer": {"type": "string"},
                                "difficulty": {
                                    "type": "string",
                                    "enum": ["easy", "medium", "difficult"],
                                },
                                "multi_choices": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "case_sensitive": {"type": "boolean"},
                                "question_type": {
                                    "type": "string",
                                    "enum": [
                                        "multiple_choice",
                                        "short_answer",
                                        "long_answer",
                                    ],
                                },
                                "reason": {"type": "string"},
                                "reason_code": {"type": ["string", "null"]},
                            },
                            "required": [
                                "status",
                                "question",
                                "answer",
                                "multi_choices",
                                "difficulty",
                                "case_sensitive",
                                "question_type",
                                "reason",
                                "reason_code",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                temperature=self.temperature,
                max_completion_tokens=self.max_completion_tokens,
            )

        except RateLimitError:
            raise ValueError(
                "AI_RATE_LIMIT: StudyMed's AI service is temporarily busy. "
                "Please try again shortly."
            ) from None

        except AuthenticationError:
            raise ValueError(
                "AI_AUTH_ERROR: StudyMed could not authenticate with the AI "
                "service. Please try again later."
            ) from None

        except PermissionDeniedError:
            raise ValueError(
                "AI_PERMISSION_ERROR: StudyMed does not currently have "
                "permission to use the configured AI service."
            ) from None

        except NotFoundError:
            raise ValueError(
                "AI_MODEL_ERROR: The configured AI model could not be found. "
                "Please try again later."
            ) from None

        except BadRequestError:
            raise ValueError(
                "AI_REQUEST_ERROR: StudyMed could not process the flashcard "
                "generation request. Please try again with clearer medical knowledge."
            ) from None

        except APITimeoutError:
            raise ValueError(
                "AI_TIMEOUT: StudyMed's AI service took too long to respond. "
                "Please try again."
            ) from None

        except APIConnectionError:
            raise ValueError(
                "AI_CONNECTION_ERROR: StudyMed could not connect to its AI "
                "service. Please check your connection and try again."
            ) from None

        except InternalServerError:
            raise ValueError(
                "AI_SERVER_ERROR: StudyMed's AI service is temporarily "
                "unavailable. Please try again shortly."
            ) from None

        except APIStatusError:
            raise ValueError(
                "AI_SERVICE_ERROR: StudyMed's AI service returned an unexpected "
                "error. Please try again shortly."
            ) from None

        except TimeoutError:
            raise ValueError(
                "AI_TIMEOUT: Flashcard generation took too long. Please try again."
            ) from None

        except Exception as exc:
            # Keep the technical exception available as the cause for logging/debugging,
            # but expose only a safe, stable message to the student.
            raise ValueError(
                "AI_UNKNOWN_ERROR: StudyMed could not generate the flashcard "
                "because of an unexpected AI service error."
            ) from exc

        # Validate provider response shape.
        try:
            if not response.choices:
                raise ValueError(
                    "AI_RESPONSE_ERROR: StudyMed received no response "
                    "from the AI service."
                )

            ai_output = response.choices[0].message.content

        except (AttributeError, IndexError, TypeError):
            raise ValueError(
                "AI_RESPONSE_ERROR: StudyMed received an invalid response "
                "from the AI service."
            ) from None

        if not ai_output or not ai_output.strip():
            raise ValueError(
                "AI_RESPONSE_ERROR: StudyMed's AI service returned an empty response."
            )

        try:
            data: Any = json.loads(ai_output)
        except json.JSONDecodeError:
            raise ValueError(
                "AI_RESPONSE_ERROR: StudyMed received an unreadable response "
                "from the AI service. Please try again."
            ) from None

        # Validate the generated object before returning it to handlers.
        try:
            if not isinstance(data, dict):
                raise ValueError(
                    "AI_RESPONSE_ERROR: StudyMed received an invalid "
                    "flashcard response."
                )

            required_fields = {
                "status",
                "question",
                "answer",
                "multi_choices",
                "difficulty",
                "case_sensitive",
                "question_type",
                "reason",
                "reason_code",
            }

            if not required_fields.issubset(data):
                raise ValueError(
                    "AI_RESPONSE_ERROR: The AI response was missing required "
                    "flashcard information."
                )

            if data["status"] not in {"success", "rejected"}:
                raise ValueError(
                    "AI_RESPONSE_ERROR: The AI returned an invalid flashcard status."
                )

            if data["difficulty"] not in {"easy", "medium", "difficult"}:
                raise ValueError(
                    "AI_RESPONSE_ERROR: The AI returned an invalid flashcard difficulty."
                )

            if data["question_type"] not in {
                "multiple_choice",
                "short_answer",
                "long_answer",
            }:
                raise ValueError(
                    "AI_RESPONSE_ERROR: The AI returned an invalid question type."
                )

            if not isinstance(data["question"], str):
                raise ValueError(
                    "AI_RESPONSE_ERROR: The generated question is invalid."
                )

            if not isinstance(data["answer"], str):
                raise ValueError("AI_RESPONSE_ERROR: The generated answer is invalid.")

            if not isinstance(data["multi_choices"], list):
                raise ValueError(
                    "AI_RESPONSE_ERROR: The generated choices are invalid."
                )

            if not isinstance(data["case_sensitive"], bool):
                raise ValueError(
                    "AI_RESPONSE_ERROR: The case-sensitivity setting is invalid."
                )

            if not isinstance(data["reason"], str):
                raise ValueError(
                    "AI_RESPONSE_ERROR: The AI returned an invalid rejection explanation."
                )

            if data["reason_code"] is not None and not isinstance(
                data["reason_code"], str
            ):
                raise ValueError(
                    "AI_RESPONSE_ERROR: The AI returned an invalid rejection code."
                )

            if data["status"] == "success":
                if not data["question"].strip():
                    raise ValueError(
                        "AI_RESPONSE_ERROR: The AI generated an empty question."
                    )

                if not data["answer"].strip():
                    raise ValueError(
                        "AI_RESPONSE_ERROR: The AI generated an empty answer."
                    )

                if data["question_type"] == "multiple_choice":
                    if len(data["multi_choices"]) != 4:
                        raise ValueError(
                            "AI_RESPONSE_ERROR: The AI generated an invalid "
                            "multiple-choice question."
                        )

                    if not all(
                        isinstance(choice, str) and choice.strip()
                        for choice in data["multi_choices"]
                    ):
                        raise ValueError(
                            "AI_RESPONSE_ERROR: One or more generated answer "
                            "choices were invalid."
                        )

                elif data["multi_choices"]:
                    raise ValueError(
                        "AI_RESPONSE_ERROR: The AI returned answer choices "
                        "for a non-multiple-choice question."
                    )

            elif not data["reason"].strip():
                raise ValueError(
                    "AI_RESPONSE_ERROR: The AI rejected the knowledge without "
                    "providing a reason."
                )

        except KeyError:
            raise ValueError(
                "AI_RESPONSE_ERROR: The AI response did not contain all "
                "required flashcard information."
            ) from None

        try:
            return GeneratedFlashCard(
                status=data["status"],
                question=data["question"],
                answer=data["answer"],
                multi_choices=data["multi_choices"],
                difficulty=data["difficulty"],
                case_sensitive=data["case_sensitive"],
                question_type=data["question_type"],
                reason=data["reason"],
                reason_code=data["reason_code"],
            )
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "AI_RESPONSE_ERROR: StudyMed could not construct the "
                "generated flashcard."
            ) from None
