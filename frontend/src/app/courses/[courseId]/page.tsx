'use client';
import { useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Brain,
  Upload,
  BookOpen,
  BarChart3,
  Plus,
  AlertCircle,
  RefreshCw,
  Zap,
  Pencil,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { TokenCounter } from '@/components/ui/TokenCounter';
import { StreamingText } from '@/components/ui/StreamingText';
import { FileUpload } from '@/components/upload/FileUpload';
import { MaterialsList } from '@/components/upload/MaterialsList';
import { AnalysisReport } from '@/components/analytics/AnalysisReport';
import { ConceptHeatmap } from '@/components/analytics/ConceptHeatmap';
import { ExamCard } from '@/components/exam/ExamCard';
import { Modal } from '@/components/ui/Modal';
import { coursesApi, analysisApi, examsApi, extractErrorMessage } from '@/lib/api';
import { useSSE } from '@/hooks/useSSE';
import type { Course, Analysis, Exam, ConceptHeatmapItem } from '@/types';
import Cookies from 'js-cookie';

type TabId = 'materials' | 'analysis' | 'exams' | 'heatmap';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'materials', label: 'Materials', icon: <Upload className="h-4 w-4" /> },
  { id: 'analysis', label: 'AI Analysis', icon: <Brain className="h-4 w-4" /> },
  { id: 'exams', label: 'Exams', icon: <BookOpen className="h-4 w-4" /> },
  { id: 'heatmap', label: 'Heatmap', icon: <BarChart3 className="h-4 w-4" /> },
];

function getBusyStreamMessage(message: string, kind: 'analysis' | 'exam') {
  if (!message.toLowerCase().includes('already running')) return message;
  if (kind === 'analysis') {
    return 'Analysis is already running for this course. Wait a moment, then refresh the results.';
  }
  return 'Exam generation is already running for this course. Wait for it to finish before starting another.';
}

interface GenerateExamOptions {
  title: string;
  question_count: number;
  mode: 'standard' | 'cram';
}

interface CourseEditValues {
  name: string;
  professor_name: string;
  subject: string;
  description: string;
}

export default function CourseDetailPage() {
  const params = useParams();
  const courseId = params.courseId as string;
  const router = useRouter();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<TabId>('materials');
  const [showUpload, setShowUpload] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isEditCourseOpen, setIsEditCourseOpen] = useState(false);
  const [courseEditValues, setCourseEditValues] = useState<CourseEditValues>({
    name: '',
    professor_name: '',
    subject: '',
    description: '',
  });
  const [courseEditError, setCourseEditError] = useState<string | null>(null);
  const [isSavingCourse, setIsSavingCourse] = useState(false);
  const [analysisText, setAnalysisText] = useState('');
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisNotice, setAnalysisNotice] = useState<string | null>(null);

  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [generateOptions, setGenerateOptions] = useState<GenerateExamOptions>({
    title: '',
    question_count: 10,
    mode: 'standard',
  });
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateText, setGenerateText] = useState('');
  const [generateTokens, setGenerateTokens] = useState(0);
  const [examToDelete, setExamToDelete] = useState<Exam | null>(null);
  const [deleteExamError, setDeleteExamError] = useState<string | null>(null);
  const [isDeletingExam, setIsDeletingExam] = useState(false);
  const generateControllerRef = useRef<AbortController | null>(null);

  const {
    isStreaming: isAnalyzing,
    tokensUsed: analysisTokens,
    startStream,
    stopStream,
  } = useSSE();

  // Fetch course
  const { data: course, isLoading: courseLoading } = useQuery<Course>({
    queryKey: ['course', courseId],
    queryFn: async () => {
      const res = await coursesApi.get(courseId);
      return res.data;
    },
  });

  // Fetch analysis
  const {
    data: analysis,
    isLoading: analysisLoading,
    refetch: refetchAnalysis,
  } = useQuery<Analysis | null>({
    queryKey: ['analysis', courseId],
    queryFn: async () => {
      try {
        const res = await analysisApi.get(courseId);
        return res.data;
      } catch (err: unknown) {
        if (err && typeof err === 'object' && 'response' in err) {
          const axiosErr = err as { response?: { status?: number } };
          if (axiosErr.response?.status === 404) return null;
        }
        return null;
      }
    },
    enabled: activeTab === 'analysis',
  });

  // Fetch exams
  const { data: exams = [], refetch: refetchExams } = useQuery<Exam[]>({
    queryKey: ['exams', courseId],
    queryFn: async () => {
      const res = await examsApi.list(courseId);
      return res.data;
    },
    enabled: activeTab === 'exams',
  });

  // Fetch heatmap
  const { data: heatmapData = [] } = useQuery<ConceptHeatmapItem[]>({
    queryKey: ['heatmap', courseId],
    queryFn: async () => {
      const res = await examsApi.heatmap(courseId);
      return res.data;
    },
    enabled: activeTab === 'heatmap',
  });

  const handleStartAnalysis = async () => {
    if (isAnalyzing) return;

    if (!course || course.completed_material_count === 0) {
      setAnalysisError('Wait for at least one material to finish processing before analysis.');
      return;
    }
    if (course.processing_material_count > 0) {
      setAnalysisError('Wait for all material processing to finish before analysis.');
      return;
    }

    setAnalysisText('');
    setAnalysisError(null);
    setAnalysisNotice(null);
    setAnalysisComplete(false);

    await startStream(analysisApi.getStreamUrl(courseId), {
      method: 'POST',
      body: {},
      onEvent: (event) => {
        if (event.type === 'thinking' || event.type === 'text' || event.type === 'content') {
          setAnalysisText((prev) => prev + (event.content || ''));
        }
        if (event.type === 'warning') {
          setAnalysisNotice(event.content || 'Some material text was shortened for analysis.');
        }
        if (event.type === 'complete') {
          setAnalysisComplete(true);
          refetchAnalysis();
          queryClient.invalidateQueries({ queryKey: ['course', courseId] });
        }
      },
      onComplete: () => {
        setAnalysisComplete(true);
      },
      onError: (err) => {
        setAnalysisError(getBusyStreamMessage(err, 'analysis'));
      },
    });
  };

  const openCourseEditor = () => {
    if (!course) return;
    setCourseEditValues({
      name: course.name,
      professor_name: course.professor_name || '',
      subject: course.subject || '',
      description: course.description || '',
    });
    setCourseEditError(null);
    setIsEditCourseOpen(true);
  };

  const handleCourseUpdate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = courseEditValues.name.trim();
    if (!name) {
      setCourseEditError('Course name is required.');
      return;
    }

    setIsSavingCourse(true);
    setCourseEditError(null);
    try {
      await coursesApi.update(courseId, {
        name,
        professor_name: courseEditValues.professor_name.trim() || null,
        subject: courseEditValues.subject.trim() || null,
        description: courseEditValues.description.trim() || null,
      });
      queryClient.invalidateQueries({ queryKey: ['course', courseId] });
      queryClient.invalidateQueries({ queryKey: ['courses'] });
      setIsEditCourseOpen(false);
    } catch (err: unknown) {
      setCourseEditError(extractErrorMessage(err, 'Failed to update course. Please try again.'));
    } finally {
      setIsSavingCourse(false);
    }
  };

  const handleCancelAnalysis = () => {
    stopStream();
    setAnalysisError('Analysis cancelled.');
  };

  const handleGenerateExam = async () => {
    if (isGenerating) return;

    if (!generateOptions.title.trim()) {
      setGenerateError('Please enter an exam title.');
      return;
    }
    setGenerateError(null);
    setGenerateText('');
    setGenerateTokens(0);
    setIsGenerating(true);

    const token = Cookies.get('access_token');
    const controller = new AbortController();
    generateControllerRef.current = controller;

    try {
      const response = await fetch(examsApi.getStreamUrl(courseId), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(generateOptions),
        signal: controller.signal,
      });

      if (!response.ok) {
        let detail = `Request failed with status ${response.status}.`;
        try {
          const payload = await response.json();
          detail = payload.detail || detail;
        } catch {
          // keep the status-based fallback
        }
        throw new Error(detail);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error('No response body');

      let buffer = '';
      let createdExamId: string | null = null;
      let generationCompleted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        let streamFailure: string | null = null;

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.tokens_used) {
                setGenerateTokens((prev) => prev + data.tokens_used);
              }
              if (data.total_tokens) {
                setGenerateTokens(data.total_tokens);
              }
              if (data.type === 'content' || data.type === 'thinking') {
                setGenerateText((prev) => prev + (data.content || ''));
              }
              if (data.type === 'question') {
                setGenerateText((prev) => prev + `\nGenerating question ${data.question?.question_number || ''}...\n`);
              }
              if (data.exam_id) {
                createdExamId = data.exam_id;
              }
              if (data.type === 'complete') {
                generationCompleted = true;
                setIsGenerateOpen(false);
                refetchExams();
                setActiveTab('exams');
                if (createdExamId) {
                  router.push(`/exam/${createdExamId}`);
                }
              }
              if (data.type === 'error') {
                streamFailure = data.error || data.content || 'Generation failed';
              }
            } catch {
              // ignore parse errors
            }
          }
        }
        if (streamFailure) {
          await reader.cancel();
          throw new Error(streamFailure);
        }
      }

      if (!generationCompleted && !controller.signal.aborted) {
        throw new Error('The AI request ended before it completed. Please try again.');
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        setGenerateError('Exam generation cancelled.');
      } else {
        setGenerateError(
          getBusyStreamMessage(extractErrorMessage(err, 'Failed to generate exam.'), 'exam')
        );
      }
    } finally {
      if (generateControllerRef.current === controller) {
        generateControllerRef.current = null;
        setIsGenerating(false);
      }
    }
  };

  const handleCancelGenerateExam = () => {
    generateControllerRef.current?.abort();
  };

  const handleDeleteExam = async () => {
    if (!examToDelete) return;
    setIsDeletingExam(true);
    setDeleteExamError(null);
    try {
      await examsApi.delete(examToDelete.id);
      queryClient.invalidateQueries({ queryKey: ['exams', courseId] });
      queryClient.invalidateQueries({ queryKey: ['recentExams'] });
      setExamToDelete(null);
    } catch (err: unknown) {
      setDeleteExamError(extractErrorMessage(err, 'Failed to delete exam. Please try again.'));
    } finally {
      setIsDeletingExam(false);
    }
  };

  if (courseLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 gradient-hero rounded-xl animate-pulse" />
          <p className="text-sm text-gray-500">Loading course...</p>
        </div>
      </div>
    );
  }

  if (!course) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-gray-600">Course not found.</p>
        <Button onClick={() => router.push('/dashboard')}>
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Button>
      </div>
    );
  }

  const completedMaterialCount = course.completed_material_count;
  const processingMaterialCount = course.processing_material_count;
  const failedMaterialCount = course.failed_material_count;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back + Header */}
      <div className="mb-6">
        <button
          onClick={() => router.push('/dashboard')}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-4 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </button>

        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {course.subject && (
                <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
                  {course.subject}
                </span>
              )}
              {course.has_analysis && (
                <span className="px-2 py-0.5 bg-violet-100 text-violet-700 text-xs rounded flex items-center gap-1">
                  <Brain className="h-3 w-3" />
                  AI Analyzed
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-gray-900">{course.name}</h1>
            {course.professor_name && (
              <p className="text-gray-500 text-sm mt-0.5">Prof. {course.professor_name}</p>
            )}
            {course.description && (
              <p className="text-gray-400 text-xs mt-1">{course.description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={openCourseEditor}
            className="p-2 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
            aria-label="Edit course"
            title="Edit course"
          >
            <Pencil className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl mb-6 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all flex-1 justify-center ${
              activeTab === tab.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}

      {/* Materials Tab */}
      {activeTab === 'materials' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Course Materials
            </h2>
            <Button size="sm" onClick={() => setShowUpload((v) => !v)}>
              <Plus className="h-4 w-4" />
              {showUpload ? 'Hide Upload' : 'Upload Files'}
            </Button>
          </div>

          {showUpload && (
            <Card>
              <CardContent>
                <FileUpload
                  courseId={courseId}
                  onSuccess={() => {
                    queryClient.invalidateQueries({ queryKey: ['materials', courseId] });
                    queryClient.invalidateQueries({ queryKey: ['course', courseId] });
                    queryClient.invalidateQueries({ queryKey: ['analysis', courseId] });
                    queryClient.invalidateQueries({ queryKey: ['courses'] });
                    setUploadError(null);
                    setShowUpload(false);
                  }}
                  onError={setUploadError}
                />
                {uploadError && (
                  <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 mt-4">
                    <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                    {uploadError}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <MaterialsList
            courseId={courseId}
            onUploadClick={() => setShowUpload(true)}
          />
        </div>
      )}

      {/* Analysis Tab */}
      {activeTab === 'analysis' && (
        <div className="space-y-6">
          {analysisLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : analysis ? (
            <div>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    Professor Pattern Analysis
                  </h2>
                  <p className="text-sm text-gray-500 mt-0.5">
                    Based on {completedMaterialCount} completed material{completedMaterialCount !== 1 ? 's' : ''}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <TokenCounter
                    tokens={analysis.total_tokens_used}
                    label="Analysis tokens"
                    animated={false}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleStartAnalysis}
                    loading={isAnalyzing}
                    disabled={processingMaterialCount > 0}
                    title={
                      processingMaterialCount > 0
                        ? 'Wait for all materials to finish processing'
                        : undefined
                    }
                  >
                    <RefreshCw className="h-4 w-4" />
                    Re-analyze
                  </Button>
                </div>
              </div>
              <AnalysisReport analysis={analysis} />
            </div>
          ) : (
            /* No analysis yet */
            <div>
              {isAnalyzing || analysisText ? (
                /* Streaming view */
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900">
                      Analyzing Professor Style…
                    </h2>
                    <TokenCounter tokens={analysisTokens} animated={isAnalyzing} />
                  </div>
                  <Card>
                    <CardContent>
                      <div className="flex items-center gap-2 mb-3">
                        <div className="flex gap-1">
                          <span className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="w-2 h-2 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                        <span className="text-xs text-gray-500">
                          Extended thinking in progress…
                        </span>
                        <Button
                          size="sm"
                          variant="secondary"
                          className="ml-auto"
                          onClick={handleCancelAnalysis}
                        >
                          Cancel
                        </Button>
                      </div>
                      <div className="max-h-96 overflow-y-auto">
                        <StreamingText
                          text={analysisText}
                          isStreaming={isAnalyzing}
                          className="text-gray-700"
                        />
                      </div>
                    </CardContent>
                  </Card>

                  {analysisNotice && (
                    <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                      <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                      <span>{analysisNotice}</span>
                    </div>
                  )}

                  {analysisError && (
                    <div className="flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                      <AlertCircle className="h-4 w-4 flex-shrink-0" />
                      <span className="flex-1">{analysisError}</span>
                      <Button size="sm" variant="outline" onClick={handleStartAnalysis}>
                        Try Again
                      </Button>
                    </div>
                  )}

                  {analysisComplete && !isAnalyzing && (
                    <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
                      Analysis complete! Refreshing results…
                    </div>
                  )}
                </div>
              ) : (
                /* Start analysis CTA */
                <div className="text-center py-16">
                  <div className="w-20 h-20 gradient-hero rounded-2xl flex items-center justify-center mx-auto mb-5 opacity-90">
                    <Brain className="h-10 w-10 text-white" />
                  </div>
                  <h2 className="text-xl font-bold text-gray-900 mb-2">
                    Analyze Professor Style
                  </h2>
                  <p className="text-gray-500 text-sm max-w-md mx-auto mb-8 leading-relaxed">
                    Our AI will use extended thinking to deeply analyze your uploaded materials,
                    identifying your professor&apos;s preferred question types, favorite concepts,
                    and unique terminology.
                  </p>

                  {analysisError && (
                    <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 mb-4 max-w-sm mx-auto">
                      <AlertCircle className="h-4 w-4 flex-shrink-0" />
                      {analysisError}
                    </div>
                  )}

                  {processingMaterialCount > 0 ? (
                    <div className="space-y-3">
                      <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 inline-block">
                        Wait for all materials to finish processing before analysis
                      </p>
                      <div>
                        <Button
                          variant="secondary"
                          onClick={() => setActiveTab('materials')}
                        >
                          <Upload className="h-4 w-4" />
                          Review Materials
                        </Button>
                      </div>
                    </div>
                  ) : completedMaterialCount === 0 ? (
                    <div className="space-y-3">
                      <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 inline-block">
                        {course.material_count === 0
                          ? 'Upload at least one material before analyzing'
                          : failedMaterialCount > 0
                              ? 'Retry a failed material or upload another file before analyzing'
                              : 'Upload a completed material before analyzing'}
                      </p>
                      <div>
                        <Button
                          variant="secondary"
                          onClick={() => setActiveTab('materials')}
                        >
                          <Upload className="h-4 w-4" />
                          {course.material_count === 0 ? 'Upload Materials First' : 'Review Materials'}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button size="lg" onClick={handleStartAnalysis}>
                      <Brain className="h-5 w-5" />
                      Start AI Analysis
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Exams Tab */}
      {activeTab === 'exams' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Practice Exams
            </h2>
            <Button
              onClick={() => setIsGenerateOpen(true)}
              disabled={!course.has_analysis}
              title={!course.has_analysis ? 'Run AI Analysis first' : undefined}
            >
              <Plus className="h-4 w-4" />
              Generate Exam
            </Button>
          </div>

          {!course.has_analysis && (
            <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
              <AlertCircle className="h-5 w-5 flex-shrink-0 text-amber-600" />
              <div>
                <p className="font-medium">AI Analysis required</p>
                <p className="text-xs text-amber-600 mt-0.5">
                  Run the AI Analysis on your materials first to generate personalized exams.
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="ml-auto flex-shrink-0 border-amber-400 text-amber-700 hover:bg-amber-100"
                onClick={() => setActiveTab('analysis')}
              >
                Go to Analysis
              </Button>
            </div>
          )}

          {exams.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-xl">
              <BookOpen className="h-8 w-8 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-600 font-medium">No exams yet</p>
              <p className="text-xs text-gray-400 mt-1">
                Generate your first AI-powered mock exam
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {exams.map((exam) => (
                <ExamCard
                  key={exam.id}
                  exam={exam}
                  onDelete={(selectedExam) => {
                    setExamToDelete(selectedExam);
                    setDeleteExamError(null);
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Heatmap Tab */}
      {activeTab === 'heatmap' && (
        <div>
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Concept Weakness Heatmap
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Visual representation of your performance across concepts
            </p>
          </div>
          <Card>
            <CardContent>
              <ConceptHeatmap data={heatmapData} />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Edit Course Modal */}
      <Modal
        isOpen={isEditCourseOpen}
        onClose={() => {
          if (!isSavingCourse) {
            setIsEditCourseOpen(false);
            setCourseEditError(null);
          }
        }}
        title="Edit Course"
        description="Keep the course details aligned with your current class."
      >
        <form onSubmit={handleCourseUpdate} className="space-y-4">
          {courseEditError && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              {courseEditError}
            </div>
          )}
          <div>
            <label htmlFor="course_name" className="label-base">Course Name</label>
            <input
              id="course_name"
              type="text"
              className="input-base"
              value={courseEditValues.name}
              onChange={(event) =>
                setCourseEditValues((current) => ({ ...current, name: event.target.value }))
              }
              maxLength={255}
              required
            />
          </div>
          <div>
            <label htmlFor="course_professor" className="label-base">Professor Name</label>
            <input
              id="course_professor"
              type="text"
              className="input-base"
              value={courseEditValues.professor_name}
              onChange={(event) =>
                setCourseEditValues((current) => ({
                  ...current,
                  professor_name: event.target.value,
                }))
              }
              maxLength={255}
            />
          </div>
          <div>
            <label htmlFor="course_subject" className="label-base">Subject</label>
            <input
              id="course_subject"
              type="text"
              className="input-base"
              value={courseEditValues.subject}
              onChange={(event) =>
                setCourseEditValues((current) => ({ ...current, subject: event.target.value }))
              }
              maxLength={255}
            />
          </div>
          <div>
            <label htmlFor="course_description" className="label-base">Description</label>
            <textarea
              id="course_description"
              className="input-base resize-none"
              rows={3}
              value={courseEditValues.description}
              onChange={(event) =>
                setCourseEditValues((current) => ({
                  ...current,
                  description: event.target.value,
                }))
              }
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsEditCourseOpen(false)}
              disabled={isSavingCourse}
            >
              Cancel
            </Button>
            <Button type="submit" loading={isSavingCourse}>Save Changes</Button>
          </div>
        </form>
      </Modal>

      {/* Generate Exam Modal */}
      <Modal
        isOpen={isGenerateOpen}
        onClose={() => {
          if (!isGenerating) {
            setIsGenerateOpen(false);
            setGenerateError(null);
            setGenerateText('');
            setGenerateOptions((prev) => ({ ...prev, title: '' }));
          }
        }}
        title="Generate Practice Exam"
        description="Configure your AI-generated mock exam"
        size="md"
      >
        {!isGenerating ? (
          <div className="space-y-5">
            {generateError && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                {generateError}
              </div>
            )}

            <div>
              <label className="label-base">Exam Title</label>
              <input
                type="text"
                className="input-base"
                placeholder="e.g. Midterm Practice"
                value={generateOptions.title}
                onChange={(e) =>
                  setGenerateOptions((prev) => ({ ...prev, title: e.target.value }))
                }
              />
            </div>

            <div>
              <label className="label-base">Number of Questions</label>
              <input
                type="range"
                min={5}
                max={30}
                step={5}
                value={generateOptions.question_count}
                onChange={(e) =>
                  setGenerateOptions((prev) => ({
                    ...prev,
                    question_count: Number(e.target.value),
                  }))
                }
                className="w-full accent-blue-600"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>5</span>
                <span className="font-semibold text-blue-600 text-sm">
                  {generateOptions.question_count} questions
                </span>
                <span>30</span>
              </div>
            </div>

            <div>
              <label className="label-base">Exam Mode</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setGenerateOptions((prev) => ({ ...prev, mode: 'standard' }))
                  }
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    generateOptions.mode === 'standard'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <BookOpen className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-semibold text-gray-900">Standard</span>
                  </div>
                  <p className="text-xs text-gray-500">
                    Comprehensive coverage of all topics
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setGenerateOptions((prev) => ({ ...prev, mode: 'cram' }))
                  }
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    generateOptions.mode === 'cram'
                      ? 'border-amber-500 bg-amber-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Zap className="h-4 w-4 text-amber-500" />
                    <span className="text-sm font-semibold text-gray-900">Cram</span>
                  </div>
                  <p className="text-xs text-gray-500">
                    High-frequency & high-impact topics
                  </p>
                </button>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setIsGenerateOpen(false);
                  setGenerateError(null);
                  setGenerateText('');
                  setGenerateOptions((prev) => ({ ...prev, title: '' }));
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleGenerateExam} loading={isGenerating}>
                <Brain className="h-4 w-4" />
                Generate Exam
              </Button>
            </div>
          </div>
        ) : (
          /* Generating state */
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 rounded-full bg-blue-600 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-sm text-gray-600 font-medium">
                  Generating exam…
                </span>
              </div>
              <TokenCounter tokens={generateTokens} animated />
            </div>
            <div className="max-h-60 overflow-y-auto border border-gray-100 rounded-xl p-3 bg-gray-50">
              <StreamingText
                text={generateText}
                isStreaming={isGenerating}
                className="text-gray-600"
              />
            </div>
            {generateError && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                {generateError}
              </div>
            )}
            <div className="flex justify-end">
              <Button variant="secondary" size="sm" onClick={handleCancelGenerateExam}>
                Cancel Generation
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={!!examToDelete}
        onClose={() => {
          if (!isDeletingExam) {
            setExamToDelete(null);
            setDeleteExamError(null);
          }
        }}
        title="Delete Exam"
        description="This removes the exam, questions, and submitted answers."
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Delete <span className="font-medium text-gray-900">{examToDelete?.title}</span>?
          </p>
          {deleteExamError && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              {deleteExamError}
            </div>
          )}
          <div className="flex justify-end gap-3">
            <Button
              variant="secondary"
              size="sm"
              disabled={isDeletingExam}
              onClick={() => {
                setExamToDelete(null);
                setDeleteExamError(null);
              }}
            >
              Cancel
            </Button>
            <Button variant="danger" size="sm" loading={isDeletingExam} onClick={handleDeleteExam}>
              Delete Exam
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
