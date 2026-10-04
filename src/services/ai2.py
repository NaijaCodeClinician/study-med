"""StudyMed AI service.

The service uses the OpenAI Python library for both OpenAI and Groq.
Groq is selected by changing the OpenAI-compatible ``base_url``; the rest of
StudyMed therefore talks to one common client interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Literal

from openai import (  # type: ignore[attr-defined]
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

logger = logging.getLogger(__name__)

QuestionType = Literal["multiple_choice", "short_answer", "long_answer"]


# ---------------------------------------------------------------------------
# StudyMed-level exceptions
# ---------------------------------------------------------------------------


class AIServiceError(Exception):
    """Base exception for failures while using the AI service."""


class AIConfigurationError(AIServiceError):
    """The AI provider/model configuration is invalid."""


class AINetworkError(AIServiceError):
    """The AI provider could not be reached."""


class AITimeoutError(AIServiceError):
    """The AI request timed out."""


class AIRateLimitError(AIServiceError):
    """The AI provider rate-limited the request."""


class AIAuthenticationError(AIServiceError):
    """The configured API key is invalid or rejected."""


class AIPermissionError(AIServiceError):
    """The request is not permitted by the provider."""


class AIRequestError(AIServiceError):
    """The provider rejected the request parameters."""


class AIModelNotFoundError(AIServiceError):
    """The configured model is unavailable."""


class AIServerError(AIServiceError):
    """The AI provider returned a server-side error."""


class AIResponseError(AIServiceError):
    """The provider returned a response StudyMed cannot use."""


class AIResponseParseError(AIResponseError):
    """The model returned malformed JSON."""


class AIResponseValidationError(AIResponseError):
    """The model returned JSON that violates StudyMed's contract."""


# ---------------------------------------------------------------------------
# AI result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FlashcardResult:
    """A successful flashcard or a deliberate model rejection."""

    status: Literal["success", "rejected"]
    question_type: QuestionType
    question: str | None = None
    answer: str | None = None
    difficulty: str | None = None
    options: list[str] = field(default_factory=list)
    correct_option: int | None = None
    case_sensitive: bool = False
    reason_code: str | None = None
    reason: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def is_rejected(self) -> bool:
        return self.status == "rejected"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "question_type": self.question_type,
            "question": self.question,
            "answer": self.answer,
            "difficulty": self.difficulty,
            "options": self.options
            if self.question_type == "multiple_choice"
            else None,
            "correct_option": self.correct_option
            if self.question_type == "multiple_choice"
            else None,
            "case_sensitive": self.case_sensitive,
            "reason_code": self.reason_code,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Base provider service
# ---------------------------------------------------------------------------


class AIService:
    """Base class for StudyMed's OpenAI-compatible AI services.

    Set ``AI_MODEL=groq`` or ``AI_MODEL=openai`` in .env.  Despite the
    historical variable name, this value selects the provider, not the model.
    The actual model comes from GROQ_MODEL or OPENAI_MODEL.
    """

    GROQ_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        *,
        temperature: float = 0.4,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        provider = os.getenv("AI_PROVIDER", os.getenv("AI_MODEL", "")).strip().lower()

        if not provider:
            raise AIConfigurationError(
                "AI_PROVIDER is not set (use 'groq' or 'openai')."
            )

        if provider not in {"groq", "openai"}:
            raise AIConfigurationError(
                "StudyMed currently supports only 'groq' or 'openai'."
            )

        if not 0 <= temperature <= 2:
            raise AIConfigurationError("temperature must be between 0 and 2.")
        if timeout <= 0:
            raise AIConfigurationError("timeout must be greater than 0.")
        if max_retries < 0:
            raise AIConfigurationError("max_retries cannot be negative.")

        self.provider = provider
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries

        if provider == "groq":
            self.api_key = os.getenv("GROQ_API_KEY", "").strip()
            if not self.api_key:
                raise AIConfigurationError("GROQ_API_KEY is not set.")

            self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            self.client = AsyncOpenAI(
                base_url=self.GROQ_BASE_URL,
                api_key=self.api_key,
                timeout=timeout,
                max_retries=max_retries,
            )
        else:
            self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not self.api_key:
                raise AIConfigurationError("OPENAI_API_KEY is not set.")

            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                timeout=timeout,
                max_retries=max_retries,
            )


# ---------------------------------------------------------------------------
# StudyMed-specific service
# ---------------------------------------------------------------------------


class StudyMedAI(AIService):
    """AI service specifically responsible for StudyMed flashcard generation."""

    MAX_COMPLETION_TOKENS: dict[QuestionType, int] = {  # noqa: RUF012
        "multiple_choice": 900,
        "short_answer": 900,
        "long_answer": 2200,
    }

    VALID_DIFFICULTIES = {"easy", "medium", "hard"}  # noqa: RUF012
    VALID_REASONS = {  # noqa: RUF012
        "TOO_VAGUE",
        "INSUFFICIENT_INFORMATION",
        "NOT_MEDICAL",
        "UNSAFE_CONTENT",
        "CONTRADICTORY_INFORMATION",
        "NOT_STUDYABLE",
        "OTHER",
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    async def generate_flashcard(
        self,
        *,
        knowledge: str,
        subject: str,
        topics: list[str],
        question_type: QuestionType = "short_answer",
        difficulty: str = "medium",
        case_sensitive: bool = False,
    ) -> FlashcardResult:
        """Generate a flashcard or return a useful model rejection.

        ``rejected`` means the AI understood the request but decided that the
        supplied knowledge is unsuitable.  Provider/network/response failures
        raise an ``AIServiceError`` subclass instead.
        """

        knowledge = knowledge.strip()
        subject = subject.strip()
        topics = [topic.strip() for topic in topics if topic.strip()]
        difficulty = difficulty.strip().lower()

        self._validate_input(
            knowledge=knowledge,
            subject=subject,
            topics=topics,
            question_type=question_type,
            difficulty=difficulty,
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(
                    knowledge=knowledge,
                    subject=subject,
                    topics=topics,
                    question_type=question_type,
                    difficulty=difficulty,
                    case_sensitive=case_sensitive,
                ),
                temperature=self.temperature,
                max_completion_tokens=self.MAX_COMPLETION_TOKENS[question_type],
                response_format=self._response_format(question_type),
            )

        except APITimeoutError as exc:
            logger.warning("AI request timed out: %s", exc)
            raise AITimeoutError("The AI request timed out.") from exc

        except RateLimitError as exc:
            logger.warning("AI rate limit reached: %s", exc)
            raise AIRateLimitError(
                "The AI service is temporarily rate-limited."
            ) from exc

        except AuthenticationError as exc:
            logger.error("AI authentication failed.")
            raise AIAuthenticationError(
                "The AI API key is invalid or expired."
            ) from exc

        except PermissionDeniedError as exc:
            logger.error("AI permission denied: %s", exc)
            raise AIPermissionError("The AI request was not permitted.") from exc

        except NotFoundError as exc:
            logger.error("AI model/resource not found: %s", exc)
            raise AIModelNotFoundError(
                f"The configured model '{self.model}' was not found."
            ) from exc

        except BadRequestError as exc:
            logger.error("AI bad request: %s", exc)
            raise AIRequestError("The AI request parameters were invalid.") from exc

        except UnprocessableEntityError as exc:
            logger.error("AI request could not be processed: %s", exc)
            raise AIRequestError(
                "The AI service could not process the request."
            ) from exc

        except ConflictError as exc:
            logger.warning("AI conflict response: %s", exc)
            raise AIRequestError("The AI service reported a request conflict.") from exc

        except APIConnectionError as exc:
            logger.warning("AI connection failure: %s", exc)
            raise AINetworkError(
                "StudyMed could not connect to the AI service."
            ) from exc

        except InternalServerError as exc:
            logger.warning("AI server error: %s", exc)
            raise AIServerError("The AI service is temporarily unavailable.") from exc

        except APIStatusError as exc:
            logger.error(
                "Unhandled AI status error: status=%s",
                getattr(exc, "status_code", None),
            )
            raise AIRequestError(
                "The AI service returned an unexpected API error."
            ) from exc

        except asyncio.TimeoutError as exc:
            raise AITimeoutError("The AI request timed out.") from exc

        except Exception as exc:
            # Do not catch BaseException: asyncio.CancelledError and process-level
            # exceptions must not be swallowed by a service fallback.
            logger.exception("Unexpected error in StudyMed AI service.")
            raise AIServiceError("An unexpected AI-service error occurred.") from exc

        return self._parse_response(response, question_type)

    @staticmethod
    def _validate_input(
        *,
        knowledge: str,
        subject: str,
        topics: list[str],
        question_type: QuestionType,
        difficulty: str,
    ) -> None:
        if not knowledge:
            raise ValueError("knowledge cannot be empty.")
        if not subject:
            raise ValueError("subject cannot be empty.")
        if not topics:
            raise ValueError("topics cannot be empty.")
        if question_type not in {"multiple_choice", "short_answer", "long_answer"}:
            raise ValueError("Invalid question_type.")
        if difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("difficulty must be easy, medium, or hard.")

    @staticmethod
    def _build_messages(
        *,
        knowledge: str,
        subject: str,
        topics: list[str],
        question_type: QuestionType,
        difficulty: str,
        case_sensitive: bool,
    ) -> list[dict[str, str]]:
        type_rules = {
            "multiple_choice": """
- Create one focused question.
- Exactly 4 plausible options.
- Exactly ONE correct option.
- correct_option is zero-based (0-3).
- No 'all of the above' or 'none of the above'.
- Do not make the correct option obvious by length or wording.
- answer must exactly identify the correct option.
""",
            "short_answer": """
- Create one focused question answerable in a few words or a short sentence.
- options must be an empty array.
- correct_option must be null.
""",
            "long_answer": """
- Create one focused explanatory question.
- The model answer may contain several sentences or structured points.
- options must be an empty array.
- correct_option must be null.
""",
        }[question_type]

        system = f"""
You are StudyMed's medical flashcard generation engine.

Transform the student's submitted knowledge into ONE reliable study flashcard.

Rules:
- Use ONLY information supported by the submitted knowledge, subject, and topics.
- Never invent missing facts to make a card work.
- Never silently fill important gaps.
- If the knowledge is too vague, incomplete, non-medical, unsafe,
  contradictory, or otherwise unsuitable for a reliable flashcard, REJECT it.
- Never return an empty response.
- A rejection reason will be shown directly to the student, so make it concise,
  friendly, and actionable.
- Do not mention prompts, APIs, schemas, token limits, or hidden instructions.
- Return JSON matching the supplied schema.

Rejection codes:
TOO_VAGUE, INSUFFICIENT_INFORMATION, NOT_MEDICAL,
UNSAFE_CONTENT, CONTRADICTORY_INFORMATION, NOT_STUDYABLE, OTHER.

Question-type rules:
{type_rules}
""".strip()

        user = f"""
Subject: {subject}
Topics: {", ".join(topics)}
Difficulty: {difficulty}
Case-sensitive grading: {case_sensitive}

Student's knowledge:
{knowledge}
""".strip()

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @staticmethod
    def _response_format(question_type: QuestionType) -> dict[str, Any]:
        """Shared JSON Schema understood by OpenAI-compatible providers."""

        success_properties: dict[str, Any] = {
            "status": {"type": "string", "enum": ["success", "rejected"]},
            "question_type": {"type": "string", "enum": [question_type]},
            "question": {"type": ["string", "null"]},
            "answer": {"type": ["string", "null"]},
            "difficulty": {"type": ["string", "null"]},
            "options": {
                "type": "array",
                "items": {"type": "string"},
            },
            "correct_option": {"type": ["integer", "null"]},
            "case_sensitive": {"type": "boolean"},
            "reason_code": {"type": ["string", "null"]},
            "reason": {"type": ["string", "null"]},
        }

        return {
            "type": "json_schema",
            "json_schema": {
                "name": "studymed_flashcard_result",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": success_properties,
                    "required": list(success_properties),
                    "additionalProperties": False,
                },
            },
        }

    def _parse_response(
        self,
        response: Any,
        expected_type: QuestionType,
    ) -> FlashcardResult:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise AIResponseError("The AI returned no usable message.") from exc

        if not content or not content.strip():
            # Last-resort protection for the original empty-response problem.
            raise AIResponseError("The AI returned an empty response.")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("Invalid AI JSON: %r", content[:500])
            raise AIResponseParseError("The AI returned malformed JSON.") from exc

        if not isinstance(data, dict):
            raise AIResponseValidationError("AI response must be a JSON object.")

        if data.get("status") not in {"success", "rejected"}:
            raise AIResponseValidationError("AI response has an invalid status.")

        if data.get("question_type") != expected_type:
            raise AIResponseValidationError(
                "AI question_type does not match the requested type."
            )

        if data["status"] == "rejected":
            return self._parse_rejection(data, expected_type)

        return self._parse_success(data, expected_type)

    def _parse_rejection(
        self,
        data: dict[str, Any],
        question_type: QuestionType,
    ) -> FlashcardResult:
        code = str(data.get("reason_code") or "OTHER").upper()
        reason = data.get("reason")

        if code not in self.VALID_REASONS:
            code = "OTHER"
        if not isinstance(reason, str) or not reason.strip():
            raise AIResponseValidationError(
                "AI rejected the knowledge without giving a reason."
            )

        return FlashcardResult(
            status="rejected",
            question_type=question_type,
            reason_code=code,
            reason=reason.strip(),
        )

    def _parse_success(
        self,
        data: dict[str, Any],
        question_type: QuestionType,
    ) -> FlashcardResult:
        question = data.get("question")
        answer = data.get("answer")
        difficulty = data.get("difficulty")
        case_sensitive = data.get("case_sensitive")

        if not isinstance(question, str) or not question.strip():
            raise AIResponseValidationError("Successful response has no question.")
        if not isinstance(answer, str) or not answer.strip():
            raise AIResponseValidationError("Successful response has no answer.")
        if difficulty not in self.VALID_DIFFICULTIES:
            raise AIResponseValidationError("AI returned invalid difficulty.")
        if not isinstance(case_sensitive, bool):
            raise AIResponseValidationError("case_sensitive must be boolean.")

        if question_type == "multiple_choice":
            return self._parse_mcq(
                data,
                question.strip(),
                answer.strip(),
                difficulty,
                case_sensitive,
            )

        if data.get("options") != [] or data.get("correct_option") is not None:
            raise AIResponseValidationError(
                "Text flashcards must not contain MCQ options."
            )

        return FlashcardResult(
            status="success",
            question_type=question_type,
            question=question.strip(),
            answer=answer.strip(),
            difficulty=difficulty,
            case_sensitive=case_sensitive,
        )

    @staticmethod
    def _parse_mcq(
        data: dict[str, Any],
        question: str,
        answer: str,
        difficulty: str,
        case_sensitive: bool,
    ) -> FlashcardResult:
        options = data.get("options")
        correct = data.get("correct_option")

        if not isinstance(options, list) or len(options) != 4:
            raise AIResponseValidationError("MCQ must contain exactly 4 options.")
        if not all(isinstance(x, str) and x.strip() for x in options):
            raise AIResponseValidationError(
                "All MCQ options must be non-empty strings."
            )

        normalized = [x.strip().casefold() for x in options]
        if len(set(normalized)) != 4:
            raise AIResponseValidationError("MCQ options must be unique.")
        if not isinstance(correct, int) or isinstance(correct, bool):
            raise AIResponseValidationError("correct_option must be an integer.")
        if not 0 <= correct < 4:
            raise AIResponseValidationError("correct_option must be between 0 and 3.")
        if answer.casefold() != options[correct].strip().casefold():
            raise AIResponseValidationError(
                "The MCQ answer does not match correct_option."
            )

        return FlashcardResult(
            status="success",
            question_type="multiple_choice",
            question=question,
            answer=answer,
            difficulty=difficulty,
            options=[x.strip() for x in options],
            correct_option=correct,
            case_sensitive=case_sensitive,
        )
