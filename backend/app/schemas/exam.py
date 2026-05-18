import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    question_count: int = Field(ge=1, le=100)
    mode: str = Field(default="standard", pattern="^(standard|cram)$")
    topics: list[str] | None = None


class MultipleChoiceOption(BaseModel):
    label: str  # "A", "B", "C", "D"
    text: str


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
    student_answer: str = ""


class ExamSubmit(BaseModel):
    answers: list[StudentAnswerSubmit]


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
