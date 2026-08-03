CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    google_id VARCHAR(255) UNIQUE,
    phone_number VARCHAR(30),
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resumes (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    original_file_name VARCHAR(500) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    raw_text TEXT NOT NULL,
    parsed_resume_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_descriptions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    original_file_name VARCHAR(500),
    file_type VARCHAR(20) NOT NULL,
    raw_text TEXT NOT NULL,
    parsed_jd_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS match_results (
    id UUID PRIMARY KEY,
    resume_id UUID NOT NULL REFERENCES resumes(id),
    job_description_id UUID NOT NULL REFERENCES job_descriptions(id),
    score DOUBLE PRECISION NOT NULL,
    result_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS question_sets (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    resume_id UUID REFERENCES resumes(id),
    job_description_id UUID NOT NULL REFERENCES job_descriptions(id),
    match_result_id UUID REFERENCES match_results(id),
    difficulty VARCHAR(50) NOT NULL,
    question_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY,
    question_set_id UUID NOT NULL REFERENCES question_sets(id),
    question_text TEXT NOT NULL,
    category VARCHAR(255),
    difficulty VARCHAR(50),
    reason TEXT,
    order_index INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    question_set_id UUID REFERENCES question_sets(id),
    resume_id UUID REFERENCES resumes(id),
    job_description_id UUID REFERENCES job_descriptions(id),
    role_context VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'started',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS answers (
    id UUID PRIMARY KEY,
    interview_session_id UUID NOT NULL REFERENCES interview_sessions(id),
    question_id UUID REFERENCES questions(id),
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    transcript_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evaluations (
    id UUID PRIMARY KEY,
    answer_id UUID NOT NULL REFERENCES answers(id),
    overall_score DOUBLE PRECISION NOT NULL,
    correctness DOUBLE PRECISION,
    keyword_coverage DOUBLE PRECISION,
    clarity DOUBLE PRECISION,
    communication DOUBLE PRECISION,
    completeness DOUBLE PRECISION,
    strengths_json JSONB,
    improvements_json JSONB,
    feedback TEXT,
    ideal_answer TEXT,
    evaluation_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY,
    interview_session_id UUID NOT NULL REFERENCES interview_sessions(id),
    overall_score DOUBLE PRECISION NOT NULL,
    summary_json JSONB NOT NULL,
    recommendation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_job_descriptions_user_id ON job_descriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_match_results_resume_id ON match_results(resume_id);
CREATE INDEX IF NOT EXISTS idx_match_results_jd_id ON match_results(job_description_id);
CREATE INDEX IF NOT EXISTS idx_question_sets_user_id ON question_sets(user_id);
CREATE INDEX IF NOT EXISTS idx_questions_question_set_id ON questions(question_set_id);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_user_id ON interview_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_answers_interview_session_id ON answers(interview_session_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_answer_id ON evaluations(answer_id);
CREATE INDEX IF NOT EXISTS idx_reports_interview_session_id ON reports(interview_session_id);
