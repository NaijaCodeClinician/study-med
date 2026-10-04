"""
This is the AI service for StudyMed
"""

import json
import os
from dataclasses import dataclass

from openai import AsyncOpenAI

from src.imports import configs

AI_PROVIDER = configs.get("ai", {}).get("provider", "groq")

if not AI_PROVIDER:  # If AI_MODEL was not set, raise an exception
    raise ValueError("AI_MODEL is not set (use either groq or openai)")

MAX_COMPLETION_TOKENS = configs.get("ai", {}).get


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
    reason_code: str


class AIService:
    """
    The parent class, base class or superclass, for AI-powered services
    """

    def __init__(self):
        self.provider = AI_PROVIDER  # Get AI provider to use (groq or openai)

        if self.provider.lower() == "groq":  # If AI_MODEL is groq
            self.api_key = os.getenv("GROQ_API_KEY")
            if not self.api_key:  # If API_KEY is not set, raise an exception
                raise ValueError("GROQ_API_KEY is not set")

            self.client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.api_key,
            )
            self.model = (
                configs.get("ai", {})
                .get("models", {})
                .get("groq", "openai/gpt-oss-20b")
            )

        elif self.provider.lower() == "openai":  # If AI_MODEL is openai
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:  # If API_KEY is not set
                raise ValueError("OPENAI_API_KEY is not set")

            self.client = AsyncOpenAI(api_key=self.api_key)
            self.model = (
                configs.get("ai", {}).get("models", {}).get("openai", "gpt-4o-mini")
            )

        else:  # If AI_MODEL is neither groq nor openai, raise an exception
            raise ValueError("StudyMed currently uses (Groq or OpenAI)")

        self.temperature = float(configs.get("ai", {}).get("temperature", 0.2))
        self.max_completion_tokens = int(
            configs.get("ai", {}).get("max_completion_tokens", 500)
        )


class StudyMedAI(AIService):
    """
    AI Service specifically for StudyMed
    """

    def __init__(self):
        super().__init__()

    async def generate_flashcard(
        self, knowledge: str, subject: str, topics: list[str]
    ) -> GeneratedFlashCard:
        """
        Generate a flashcard from the user's inputted knowledge
        """

        # Generate the flashcard using AI
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        """
You are StudyMed's medical flashcard generation engine.

Transform the student's submitted knowledge into ONE reliable study flashcard.

Rules:
- Use ONLY information supported by the submitted knowledge, subject, and topics.
- Never invent missing facts to make a card work.
- Never silently fill important gaps.
- If the knowledge is too vague, incomplete, non-medical, unsafe,
  contradictory, or otherwise unsuitable for a reliable flashcard, REJECT it.
- If a provided knowledge even though medically accurate doesn't match the provided
subject and/or topics, REJECT it.
- Set "status" to "success" if no rejection occurred and question generation was successful, else "failed"
- Never return an empty response.
- A rejection reason will be shown directly to the student, so make it concise,
  friendly, and actionable.
- Difficulty must be exactly one of: easy, medium or difficult and should be determined from
the knowledge (how vast, concise and complicated it is).
- case_sensitive determines whether capitalization must match when grading the student's answer.
    - Set case_sensitive to true when capitalization is part of the identity or correctness of the
        answer, such as scientific names, proper names, founders' names, abbreviations where capitalization
        changes meaning, or other answers where capitalization should be strictly preserved.
    - Set case_sensitive to false for ordinary medical concepts, anatomical structures, organs, processes, 
        conditions, and similar answers where capitalization should not affect correctness.
    - Do not set case_sensitive to true merely because the answer happens to begin with a capital letter
- question_type should be one of the following (multiple_choice, short_answer, long_answer), and determines
if a knowledge produces a question with multiple choice, and the max_completion_tokens for a question
    - Set question_type to "multiple_choice" if the generated question is best treated as a multiple-choice question
    - Set question_type to "short_answer" if the generated question is best treated as a short answer type of question
    - Set question_type to "long_answer" if the generated question is best treated as a long descriptive answer type of question
- Do not mention prompts, APIs, schemas, token limits, or hidden instructions.
- Return JSON matching the supplied schema.

Rejection codes:
TOO_VAGUE, INSUFFICIENT_INFORMATION, NOT_MEDICAL,
UNSAFE_CONTENT, CONTRADICTORY_INFORMATION, NOT_STUDYABLE, DOESN'T_MATCH, OTHER.

Question-type rules (question_type):
multiple_choice: 
- Create one focused question.
- Exactly 4 plausible options.
- Exactly ONE correct option.
- correct_option is zero-based (0-3).
- No 'all of the above' or 'none of the above'.
- Do not make the correct option obvious by length or wording.
- answer must exactly identify the correct option.

short_answer:
- Create one focused question answerable in a few words or a short sentence.
- options must be an empty array.
- correct_option must be null.

long_answer:
- Create one focused explanatory question.
- The model answer may contain several sentences or structured points.
- options must be an empty array.
- correct_option must be null.

MAX_COMPLETION_TOKENS:

multiple_choice: 900,
short_answer: 900,
long_answer: 2200
"""
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
                    Subject: {subject}
                    Topics: {",".join(topics)}
                    Knowledge: {knowledge}
                    """,
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
                                "type": "str",
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
        ai_output = response.choices[0].message.content  # Generated output
        if not ai_output:  # If AI didn't generate a response (error occurred)
            raise ValueError("AI returned an empty response.")

        data = json.loads(ai_output)
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
