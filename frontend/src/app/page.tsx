import Link from 'next/link';
import { ArrowRight, Brain, Upload, Zap, CheckCircle, BookOpen, BarChart3 } from 'lucide-react';

const FEATURES = [
  {
    icon: <Upload className="h-6 w-6 text-blue-600" />,
    title: 'Upload Materials',
    description:
      'Upload PDFs, PowerPoints, Word docs, or images from your lectures, notes, and past exams.',
    bg: 'bg-blue-50',
    border: 'border-blue-100',
  },
  {
    icon: <Brain className="h-6 w-6 text-violet-600" />,
    title: 'Analyze Professor Style',
    description:
      "Our AI uses extended thinking to deeply analyze your professor's exam patterns, terminology, and preferred question types.",
    bg: 'bg-violet-50',
    border: 'border-violet-100',
  },
  {
    icon: <Zap className="h-6 w-6 text-indigo-600" />,
    title: 'Generate Unlimited Exams',
    description:
      'Get hyper-personalized mock exams that match your professor\'s exact style. Instant AI grading with detailed feedback.',
    bg: 'bg-indigo-50',
    border: 'border-indigo-100',
  },
];

const STEPS = [
  {
    step: '01',
    title: 'Create a Course',
    description: 'Add your course details and professor information.',
    color: 'text-blue-600',
  },
  {
    step: '02',
    title: 'Upload Your Materials',
    description: 'Drag and drop lecture slides, past exams, and notes.',
    color: 'text-violet-600',
  },
  {
    step: '03',
    title: 'Ace Your Exams',
    description:
      'Practice with AI-generated exams tailored to your professor\'s style and track your progress.',
    color: 'text-indigo-600',
  },
];

const BENEFITS = [
  'Professor-style matched questions',
  'Extended thinking AI analysis',
  'Instant grading with feedback',
  'Concept weakness heatmap',
  'Unlimited mock exams',
  'Standard & cram modes',
];

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 gradient-hero rounded-lg flex items-center justify-center">
              <Brain className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold text-gray-900">Exam Prep AI</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/auth/login"
              className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors px-3 py-1.5"
            >
              Sign In
            </Link>
            <Link
              href="/auth/register"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
            >
              Start Free
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-24 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 gradient-hero opacity-[0.03] pointer-events-none" />
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-radial from-blue-100 to-transparent opacity-40 pointer-events-none rounded-full blur-3xl" />

        <div className="max-w-4xl mx-auto text-center relative">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-full mb-6">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-xs font-medium text-blue-700">
              Powered by Claude Extended Thinking
            </span>
          </div>

          <h1 className="text-5xl sm:text-6xl font-extrabold text-gray-900 tracking-tight leading-tight mb-6">
            Ace Your Exams with{' '}
            <span className="bg-gradient-to-r from-blue-600 via-violet-600 to-indigo-600 bg-clip-text text-transparent">
              AI That Knows Your Professor
            </span>
          </h1>

          <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-10 leading-relaxed">
            Upload your lecture materials. We&apos;ll learn your professor&apos;s exam style and generate
            unlimited personalized mock exams — so you study smarter, not harder.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/auth/register"
              className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-all shadow-lg shadow-blue-600/25 hover:shadow-xl hover:shadow-blue-600/30 hover:-translate-y-0.5"
            >
              Start Free — No Credit Card
              <ArrowRight className="h-5 w-5" />
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-gray-700 bg-white border border-gray-200 hover:border-gray-300 rounded-xl transition-all hover:shadow-md"
            >
              <BookOpen className="h-5 w-5 text-gray-400" />
              See How It Works
            </a>
          </div>

          {/* Benefits list */}
          <div className="flex flex-wrap items-center justify-center gap-3 mt-10">
            {BENEFITS.map((benefit) => (
              <span
                key={benefit}
                className="inline-flex items-center gap-1.5 text-sm text-gray-600"
              >
                <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                {benefit}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white" id="features">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              Everything You Need to Prepare
            </h2>
            <p className="text-gray-600 max-w-xl mx-auto">
              Our AI doesn&apos;t just generate random questions — it learns exactly how
              your professor thinks and tests.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className={`p-6 rounded-2xl border ${feature.bg} ${feature.border}`}
              >
                <div className="w-12 h-12 bg-white rounded-xl shadow-sm flex items-center justify-center mb-4">
                  {feature.icon}
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-600 text-sm leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gray-50" id="how-it-works">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">How It Works</h2>
            <p className="text-gray-600">
              From upload to exam-ready in minutes.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {STEPS.map((step, i) => (
              <div key={step.step} className="relative">
                {/* Connector line */}
                {i < STEPS.length - 1 && (
                  <div className="hidden md:block absolute top-6 left-full w-full h-0.5 bg-gradient-to-r from-gray-300 to-transparent z-0" />
                )}
                <div className="relative z-10">
                  <div
                    className={`text-4xl font-black mb-3 ${step.color} opacity-20`}
                  >
                    {step.step}
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    {step.title}
                  </h3>
                  <p className="text-sm text-gray-600 leading-relaxed">
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Analytics preview section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-violet-50 border border-violet-200 rounded-full mb-4">
                <BarChart3 className="h-4 w-4 text-violet-600" />
                <span className="text-xs font-medium text-violet-700">Smart Analytics</span>
              </div>
              <h2 className="text-3xl font-bold text-gray-900 mb-4">
                Know Your Weaknesses Before the Exam
              </h2>
              <p className="text-gray-600 leading-relaxed mb-6">
                Our concept weakness heatmap shows exactly which topics you need to focus
                on. After each practice exam, get AI-powered feedback on every question
                so you understand your mistakes deeply.
              </p>
              <ul className="space-y-3">
                {[
                  'Concept weakness heatmap',
                  'Per-question AI feedback',
                  'Score trend over time',
                  'Professor term analysis',
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2.5 text-sm text-gray-700">
                    <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Mock Exams Generated', value: '10K+', color: 'text-blue-600' },
                { label: 'Avg Score Improvement', value: '+23%', color: 'text-green-600' },
                { label: 'Concepts Analyzed', value: '50K+', color: 'text-violet-600' },
                { label: 'Student Satisfaction', value: '4.9★', color: 'text-amber-600' },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="p-5 bg-gray-50 rounded-xl border border-gray-200 text-center"
                >
                  <div className={`text-3xl font-black ${stat.color} mb-1`}>
                    {stat.value}
                  </div>
                  <div className="text-xs text-gray-500">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 gradient-hero">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Ace Your Next Exam?
          </h2>
          <p className="text-blue-100 mb-8">
            Join thousands of students who study smarter with AI-personalized exam prep.
          </p>
          <Link
            href="/auth/register"
            className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-blue-600 bg-white hover:bg-blue-50 rounded-xl transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
          >
            Get Started for Free
            <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 bg-gray-900 text-center">
        <p className="text-gray-400 text-sm">
          © {new Date().getFullYear()} Exam Prep AI. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
