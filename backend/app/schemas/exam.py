import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    question_count: int = Field(ge=1, le=30)
    mode: str = Field(default="standard", pattern="^(standard|cram)$")
    topics: list[str] | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class MultipleChoiceOption(BaseModel):
    label: str = Field(min_length=1, max_length=10)  # "A", "B", "C", "D"
    text: str = Field(min_length=1, max_length=2000)


class GeneratedQuestion(BaseModel):
    """Strict contract for one AI-generated question before persistence."""

    question_text: str = Field(min_length=1, max_length=20000)
    question_type: Literal["multiple_choice", "essay", "calculation", "true_false"]
    choices: list[MultipleChoiceOption] | None = None
    correct_answer: str = Field(min_length=1, max_length=20000)
    explanation: str = Field(min_length=1, max_length=20000)
    concepts: list[str] = Field(default_factory=list, max_length=30)
    difficulty: Literal["easy", "medium", "hard"]

    @model_validator(mode="after")
    def validate_choices(self) -> "GeneratedQuestion":
        if self.question_type == "multiple_choice" and not self.choices:
            raise ValueError("Multiple-choice questions require choices")
        if self.choices and len(self.choices) < 2:
            raise ValueError("Questions with choices require at least two options")
        if self.choices:
            labels = [choice.label.strip().upper() for choice in self.choices]
            if len(labels) != len(set(labels)):
                raise ValueError("Question choices must have unique labels")
        return self


class GradeResponse(BaseModel):
    """Strict contract for one AI grading response."""

    is_correct: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(min_length=1, max_length=20000)
    tokens_used: int = Field(default=0, ge=0)


class QuestionResponse(BaseModel):
    """Question as shown to the student during the exam (no answer revealed)."""
    id: uuid.UUID
    question_number: int
    question_text: str
    question_type: str
    choices: list[MultipleChoiceOption] | None
    difficulty: str
    concepts: list[str]

    model_config = {"from_attributes": True}


class QuestionWithAnswer(QuestionResponse):
    """Question including the answer and explanation (used after exam completion)."""
    correct_answer: str
    explanation: str


class ExamResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    mode: str
    question_count: int
    status: str
    score: float | None
    total_tokens_used: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExamDetailResponse(ExamResponse):
    questions: list[QuestionResponse]


class StudentAnswerSubmit(BaseModel):
    question_id: uuid.UUID
    student_answer: str = Field(default="", max_length=10000)


class ExamSubmit(BaseModel):
    answers: list[StudentAnswerSubmit] = Field(min_length=1)

    @model_validator(mode="after")
    def require_at_least_one_answer(self) -> "ExamSubmit":
        if not any(answer.student_answer.strip() for answer in self.answers):
            raise ValueError("Submit at least one answer before grading.")
        return self


class QuestionResult(BaseModel):
    question_id: uuid.UUID
    question_number: int
    is_correct: bool
    score: float
    student_answer: str
    correct_answer: str
    ai_feedback: str
    concepts: list[str]


class ExamResult(BaseModel):
    exam_id: uuid.UUID
    score: float  # 0-100
    total_questions: int
    correct_count: int
    results: list[QuestionResult]
    total_tokens_used: int


class ConceptHeatmapItem(BaseModel):
    concept: str
    attempts: int
    correct_count: int
    incorrect_count: int
    weakness_score: float
    last_attempted: datetime | None

    model_config = {"from_attributes": True}
