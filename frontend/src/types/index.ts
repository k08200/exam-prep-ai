export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface RuntimeHealth {
  status: string;
  version: string;
  ai: 'ok' | 'not_configured' | string;
  ai_mode: 'mock' | 'claude' | 'openrouter' | string;
  ai_provider: 'mock' | 'anthropic' | 'openrouter' | string;
  claude_configured: boolean;
  openrouter_configured: boolean;
}

export interface AIUsage {
  usage_date: string;
  analyses_used: number;
  analyses_limit: number;
  questions_generated: number;
  questions_limit: number;
  responses_graded: number;
  grades_limit: number;
}

export interface Course {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  professor_name: string | null;
  subject: string | null;
  created_at: string;
  material_count: number;
  completed_material_count: number;
  processing_material_count: number;
  failed_material_count: number;
  has_analysis: boolean;
}

export interface Material {
  id: string;
  course_id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  processing_error: string | null;
  page_count: number | null;
  created_at: string;
}

export interface ConceptItem {
  concept: string;
  frequency: number;
  importance_score: number;
  description: string;
}

export interface Analysis {
  id: string;
  course_id: string;
  top_concepts: ConceptItem[];
  question_types: {
    multiple_choice: number;
    essay: number;
    calculation: number;
    true_false: number;
  };
  topic_distribution: Record<string, number>;
  professor_terms: Array<{ term: string; context: string; frequency: number }>;
  exam_patterns: Record<string, unknown>;
  thinking_tokens_used: number;
  total_tokens_used: number;
  created_at: string;
}

export interface ExamQuestion {
  id: string;
  question_number: number;
  question_text: string;
  question_type: 'multiple_choice' | 'essay' | 'calculation' | 'true_false';
  choices: Array<{ label: string; text: string }> | null;
  difficulty: 'easy' | 'medium' | 'hard';
  concepts: string[];
}

export interface Exam {
  id: string;
  course_id: string;
  title: string;
  mode: 'standard' | 'cram';
  question_count: number;
  status: 'draft' | 'active' | 'completed';
  score: number | null;
  total_tokens_used: number;
  created_at: string;
  questions?: ExamQuestion[];
}

export interface ConceptHeatmapItem {
  concept: string;
  attempts: number;
  correct_count: number;
  incorrect_count: number;
  weakness_score: number;
  last_attempted: string | null;
}

export interface ExamResult {
  exam_id: string;
  score: number;
  total_questions: number;
  correct_count: number;
  results: Array<{
    question_id: string;
    question_number: number;
    is_correct: boolean;
    score: number;
    student_answer: string;
    correct_answer: string;
    ai_feedback: string;
    concepts: string[];
  }>;
  total_tokens_used: number;
}
