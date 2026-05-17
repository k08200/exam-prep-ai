import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ConceptItem(BaseModel):
    concept: str
    frequency: int
    importance_score: float = Field(ge=0.0, le=1.0)
    description: str


class QuestionTypeDistribution(BaseModel):
    multiple_choice: float = Field(ge=0.0, le=100.0)
    essay: float = Field(ge=0.0, le=100.0)
    calculation: float = Field(ge=0.0, le=100.0)
    true_false: float = Field(ge=0.0, le=100.0)

    @model_validator(mode="after")
    def check_sum(self) -> "QuestionTypeDistribution":
        total = (
            self.multiple_choice + self.essay + self.calculation + self.true_false
        )
        if abs(total - 100.0) > 1.0:
            raise ValueError(f"Question type percentages must sum to ~100, got {total}")
        return self


class ProfessorTerm(BaseModel):
    term: str
    context: str
    frequency: int


class AnalysisResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    top_concepts: list[ConceptItem]
    question_types: QuestionTypeDistribution
    topic_distribution: dict[str, float]
    professor_terms: list[ProfessorTerm]
    exam_patterns: dict
    thinking_tokens_used: int
    total_tokens_used: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisStatus(BaseModel):
    status: str  # pending / running / complete / error
    progress: int = Field(ge=0, le=100)
    message: str
