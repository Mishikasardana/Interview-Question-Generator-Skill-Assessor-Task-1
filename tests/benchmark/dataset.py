"""
Benchmark dataset for evaluating matching_engine/semantic_matching (and,
going forward, recruiter_intelligence) against recruiter-quality
expectations. 25 resume<->JD pairs, 5 per score band, spanning 10 domains.

Each entry feeds resume_json/jd_json directly into matching_engine.run_matching
and semantic_matching.evaluate_semantic_match, in the exact shape those two
public functions consume (ParsedResume/ParsedJD dict shape: flat list[str]
fields, no nested objects) -- this is deliberately upstream of resume/JD
parsing, so the benchmark isolates the MATCHING system under test rather than
re-testing resume_processing/jd_parsing's GLM calls too.

expected_min/expected_max are the author's best-effort recruiter judgment,
written BEFORE any of these pairs were run through the system, to avoid
post-hoc rationalization of whatever score the model happens to produce.

This dataset first produced real, reproducible findings (not just synthetic
noise): a 25-pair run against the original semantic_matching prompt found a
56% pass-within-band rate and traced the root cause to overall_score being an
unweighted average of category_scores in 72% of cases (see README.md in this
directory). It is the foundation the recruiter_intelligence redesign is
calibrated and validated against (see the approved plan under
.claude/plans/ — Recruiter Intelligence Engine).
"""

BENCHMARK = [
    # ============================== EXCELLENT (85-100) ==============================
    {
        "id": "excellent_01_fullstack",
        "band": "excellent", "expected_min": 88, "expected_max": 100, "domain": "Full Stack",
        "resume": {
            "name": "Priya Nair",
            "skills": ["JavaScript", "TypeScript", "React", "Next.js", "Node.js", "Express",
                       "PostgreSQL", "Redis", "Docker", "GraphQL", "Jest", "Git", "REST APIs"],
            "education": ["B.Tech in Computer Science, NIT Trichy"],
            "experience": [
                "Senior Full Stack Engineer, Freshworks (3 years): Led development of a "
                "customer support dashboard using React, Next.js, and TypeScript on the "
                "frontend, and Node.js/Express with PostgreSQL on the backend. Designed a "
                "GraphQL API layer serving 200k+ daily active users. Introduced Redis caching "
                "that cut average API latency by 40%. Owned CI/CD via Docker-based deployments."
            ],
            "projects": [
                "Built and maintains an open-source Next.js + Express boilerplate with "
                "GraphQL, PostgreSQL, and Jest test coverage, used by several small startups.",
                "Built a real-time collaborative editor using React, WebSockets, and Redis "
                "pub/sub for live cursor sync.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Senior Full Stack Engineer",
            "required_skills": ["React", "Node.js", "TypeScript", "PostgreSQL", "REST APIs",
                                 "Git"],
            "preferred_skills": ["Next.js", "GraphQL", "Redis", "Docker"],
            "responsibilities": [
                "Build and maintain full-stack web applications end to end",
                "Design REST/GraphQL APIs and relational database schemas",
                "Collaborate with product and design on customer-facing dashboards",
            ],
            "experience_level": "Senior (3+ years)",
            "education_requirement": "Bachelor's degree in Computer Science or equivalent",
        },
    },
    {
        "id": "excellent_02_backend",
        "band": "excellent", "expected_min": 88, "expected_max": 100, "domain": "Backend",
        "resume": {
            "name": "Marcus Webb",
            "skills": ["Python", "Django", "PostgreSQL", "Redis", "Docker", "Kubernetes",
                       "Celery", "RabbitMQ", "REST APIs", "Microservices", "AWS", "pytest"],
            "education": ["B.S. in Computer Science, University of Washington"],
            "experience": [
                "Senior Backend Engineer, Instacart (4 years): Designed and scaled the order "
                "fulfillment microservice using Django and PostgreSQL, handling 5M+ orders/month. "
                "Migrated a monolithic service into containerized Kubernetes deployments on AWS. "
                "Built an async task pipeline with Celery and RabbitMQ for inventory sync. "
                "Maintained 90%+ test coverage with pytest."
            ],
            "projects": [
                "Built a rate-limited public API gateway in Django REST Framework with Redis-backed "
                "throttling, deployed via Docker/Kubernetes.",
            ],
            "certifications": ["AWS Certified Solutions Architect – Associate"],
        },
        "jd": {
            "role": "Senior Backend Engineer",
            "required_skills": ["Python", "Django", "PostgreSQL", "Docker", "Kubernetes",
                                 "Microservices"],
            "preferred_skills": ["Redis", "Celery", "AWS", "RabbitMQ"],
            "responsibilities": [
                "Design and scale backend microservices handling high transaction volume",
                "Own deployment pipelines on Kubernetes",
                "Mentor junior engineers on backend best practices",
            ],
            "experience_level": "Senior (4+ years)",
            "education_requirement": "Bachelor's degree in Computer Science or related field",
        },
    },
    {
        "id": "excellent_03_frontend",
        "band": "excellent", "expected_min": 85, "expected_max": 100, "domain": "Frontend",
        "resume": {
            "name": "Elena Kowalski",
            "skills": ["JavaScript", "TypeScript", "React", "Redux", "CSS", "Sass",
                       "Webpack", "Jest", "React Testing Library", "Accessibility (WCAG)",
                       "Storybook", "Figma"],
            "education": ["B.A. in Interactive Media, Parsons School of Design"],
            "experience": [
                "Senior Frontend Engineer, Notion (3.5 years): Owned the component library used "
                "across the entire product, built with React, TypeScript, and Storybook. Led a "
                "WCAG 2.1 AA accessibility audit and remediation across 40+ components. Improved "
                "test coverage from 30% to 85% using Jest and React Testing Library. Partnered "
                "closely with design on Figma-to-code handoff."
            ],
            "projects": [
                "Maintains a widely-used open-source React accessibility linter plugin (2k+ GitHub stars).",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Senior Frontend Engineer",
            "required_skills": ["React", "TypeScript", "CSS", "Accessibility", "Jest"],
            "preferred_skills": ["Redux", "Storybook", "Figma", "Webpack"],
            "responsibilities": [
                "Build accessible, well-tested UI components at scale",
                "Partner with design to translate Figma mockups into production code",
                "Champion frontend testing and accessibility best practices",
            ],
            "experience_level": "Senior (3+ years)",
            "education_requirement": "",
        },
    },
    {
        "id": "excellent_04_datascience",
        "band": "excellent", "expected_min": 85, "expected_max": 100, "domain": "Data Science",
        "resume": {
            "name": "Rahul Mehta",
            "skills": ["Python", "pandas", "NumPy", "scikit-learn", "SQL", "Statistics",
                       "A/B Testing", "Tableau", "XGBoost", "Feature Engineering"],
            "education": ["M.S. in Statistics, University of Michigan"],
            "experience": [
                "Data Scientist, Swiggy (3 years): Built a churn prediction model using XGBoost "
                "and scikit-learn that identified at-risk customers with 82% precision, driving "
                "a targeted retention campaign. Designed and analyzed A/B tests for pricing "
                "experiments using rigorous statistical methods. Built SQL-based dashboards in "
                "Tableau for weekly business reviews."
            ],
            "projects": [
                "Built a demand forecasting pipeline in pandas/scikit-learn used by the "
                "operations team to plan delivery-partner staffing.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Data Scientist",
            "required_skills": ["Python", "SQL", "Statistics", "Machine Learning",
                                 "A/B Testing"],
            "preferred_skills": ["pandas", "scikit-learn", "Tableau", "XGBoost"],
            "responsibilities": [
                "Build predictive models to support business decisions",
                "Design and analyze experiments (A/B tests)",
                "Communicate insights to non-technical stakeholders via dashboards",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "Master's degree in Statistics, CS, or related quantitative field",
        },
    },
    {
        "id": "excellent_05_ml",
        "band": "excellent", "expected_min": 88, "expected_max": 100, "domain": "Machine Learning",
        "resume": {
            "name": "Chen Wei",
            "skills": ["Python", "PyTorch", "TensorFlow", "MLOps", "Docker", "Kubernetes",
                       "MLflow", "Model Deployment", "Computer Vision", "CUDA"],
            "education": ["M.S. in Machine Learning, Carnegie Mellon University"],
            "experience": [
                "ML Engineer, Zoox (3 years): Trained and deployed computer vision models for "
                "pedestrian detection using PyTorch, optimized for real-time inference on "
                "embedded CUDA hardware. Built the model deployment pipeline using MLflow, "
                "Docker, and Kubernetes, cutting deployment time from days to hours. Owned "
                "model monitoring and retraining triggers in production."
            ],
            "projects": [
                "Built an end-to-end MLOps pipeline (data versioning, training, deployment, "
                "monitoring) for a personal object-detection project using TensorFlow and MLflow.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Machine Learning Engineer",
            "required_skills": ["Python", "PyTorch", "Model Deployment", "MLOps", "Docker"],
            "preferred_skills": ["TensorFlow", "Kubernetes", "Computer Vision", "MLflow"],
            "responsibilities": [
                "Train and deploy production ML models",
                "Build and maintain MLOps infrastructure for training and serving",
                "Monitor model performance and drift in production",
            ],
            "experience_level": "Mid-Senior (3+ years)",
            "education_requirement": "Master's degree in ML, CS, or related field preferred",
        },
    },

    # ================================= GOOD (70-84) =================================
    {
        "id": "good_06_genai",
        "band": "good", "expected_min": 70, "expected_max": 84, "domain": "Generative AI",
        "resume": {
            "name": "Sofia Alvarez",
            "skills": ["Python", "LangChain", "OpenAI API", "Vector Databases", "Pinecone",
                       "FastAPI", "Prompt Design", "Embeddings"],
            "education": ["B.S. in Computer Science, UT Austin"],
            "experience": [
                "AI Engineer, a Series A startup (2 years): Built an internal document Q&A "
                "assistant using LangChain, OpenAI's GPT-4 API, and Pinecone for vector search "
                "over 50k+ internal documents. Iterated extensively on prompt design and "
                "few-shot examples to reduce hallucination rate. Exposed the assistant via a "
                "FastAPI service used by 300+ internal employees daily."
            ],
            "projects": [
                "Built a RAG pipeline over a company's Notion workspace using LangChain and "
                "OpenAI embeddings for semantic search.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Generative AI Engineer",
            "required_skills": ["Python", "Anthropic Claude API", "RAG", "Vector Databases",
                                 "Prompt Engineering"],
            "preferred_skills": ["LangChain", "FastAPI", "Embeddings"],
            "responsibilities": [
                "Build production RAG pipelines using Claude models",
                "Design and iterate on prompts for reliability and low hallucination",
                "Integrate LLM features into customer-facing products",
            ],
            "experience_level": "Mid-level (2+ years)",
            "education_requirement": "",
        },
    },
    {
        "id": "good_07_promptengineering",
        "band": "good", "expected_min": 70, "expected_max": 84, "domain": "Prompt Engineering",
        "resume": {
            "name": "Daniel Osei",
            "skills": ["Python", "OpenAI API", "Prompt Design", "Chain-of-Thought Prompting",
                       "Evaluation Frameworks", "JSON Schema Validation", "A/B Testing"],
            "education": ["B.A. in Linguistics, University of Toronto"],
            "experience": [
                "AI Content Systems Engineer, an edtech company (2.5 years): Designed and "
                "iterated on prompts for an automated essay-feedback feature, running "
                "systematic A/B tests to compare prompt variants and measure quality against "
                "human-graded rubrics. Built a lightweight evaluation harness that scored model "
                "outputs against expected JSON schemas and flagged regressions before deploy."
            ],
            "projects": [
                "Built a prompt-versioning and evaluation dashboard comparing chain-of-thought "
                "vs. direct-answer prompting strategies across 5 tasks.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Prompt Engineer",
            "required_skills": ["Prompt Engineering", "LLM Evaluation", "Python",
                                 "Fine-tuning"],
            "preferred_skills": ["Chain-of-Thought Prompting", "A/B Testing", "JSON Schema"],
            "responsibilities": [
                "Design, test, and iterate on prompts across multiple LLM providers",
                "Build evaluation harnesses to measure prompt quality objectively",
                "Fine-tune smaller models for cost-sensitive use cases",
            ],
            "experience_level": "Mid-level (2+ years)",
            "education_requirement": "",
        },
    },
    {
        "id": "good_08_devops",
        "band": "good", "expected_min": 70, "expected_max": 84, "domain": "DevOps",
        "resume": {
            "name": "Anna Kowalczyk",
            "skills": ["Docker", "Kubernetes", "Jenkins", "AWS", "Bash", "Python",
                       "Prometheus", "Grafana", "Ansible"],
            "education": ["B.S. in Information Systems, University of Warsaw"],
            "experience": [
                "DevOps Engineer, a fintech company (3 years): Managed Kubernetes clusters "
                "running 60+ microservices on AWS EKS. Built CI/CD pipelines in Jenkins with "
                "automated rollback on failed health checks. Set up Prometheus/Grafana "
                "monitoring stack with on-call alerting. Automated server provisioning with "
                "Ansible playbooks."
            ],
            "projects": [
                "Migrated a legacy on-prem deployment process to a fully automated GitOps "
                "workflow using ArgoCD and Kubernetes.",
            ],
            "certifications": ["Certified Kubernetes Administrator (CKA)"],
        },
        "jd": {
            "role": "DevOps Engineer",
            "required_skills": ["Docker", "Kubernetes", "AWS", "CI/CD", "Terraform"],
            "preferred_skills": ["Prometheus", "Grafana", "Ansible", "Python"],
            "responsibilities": [
                "Manage cloud infrastructure as code using Terraform",
                "Maintain CI/CD pipelines and Kubernetes deployments",
                "Build observability and alerting for production systems",
            ],
            "experience_level": "Mid-Senior (3+ years)",
            "education_requirement": "",
        },
    },
    {
        "id": "good_09_cloud",
        "band": "good", "expected_min": 70, "expected_max": 84, "domain": "Cloud",
        "resume": {
            "name": "James O'Connor",
            "skills": ["AWS", "EC2", "S3", "Lambda", "CloudFormation", "IAM", "VPC design",
                       "Python", "Cost Optimization"],
            "education": ["B.S. in Computer Engineering, Georgia Tech"],
            "experience": [
                "Cloud Infrastructure Engineer, a healthcare SaaS company (4 years): Designed "
                "multi-account AWS architecture with strict IAM boundaries for HIPAA "
                "compliance. Built serverless data pipelines with Lambda and S3. Authored "
                "CloudFormation templates for repeatable environment provisioning. Led a cost "
                "optimization initiative that cut monthly AWS spend by 30%."
            ],
            "projects": [
                "Built a self-service internal tool for spinning up isolated AWS sandbox "
                "environments via CloudFormation.",
            ],
            "certifications": ["AWS Certified Solutions Architect – Professional"],
        },
        "jd": {
            "role": "Cloud Infrastructure Engineer",
            "required_skills": ["Google Cloud Platform", "Terraform", "Kubernetes (GKE)",
                                 "IAM", "Networking"],
            "preferred_skills": ["Python", "Cost Optimization", "CI/CD"],
            "responsibilities": [
                "Design and maintain cloud infrastructure on GCP",
                "Manage IAM and network security boundaries",
                "Drive cloud cost optimization initiatives",
            ],
            "experience_level": "Senior (4+ years)",
            "education_requirement": "",
        },
    },
    {
        "id": "good_10_mobile",
        "band": "good", "expected_min": 70, "expected_max": 84, "domain": "Mobile Development",
        "resume": {
            "name": "Aisha Rahman",
            "skills": ["React Native", "JavaScript", "TypeScript", "Redux", "REST APIs",
                       "Firebase", "Jest", "App Store Deployment"],
            "education": ["B.S. in Computer Science, BRAC University"],
            "experience": [
                "Mobile Engineer, a ride-hailing startup (3 years): Built and shipped the "
                "customer-facing React Native app used by 500k+ riders, integrating real-time "
                "location tracking via Firebase and REST APIs. Owned app store release process "
                "for both iOS and Android. Wrote Jest-based unit and integration tests for core "
                "booking flows."
            ],
            "projects": [
                "Built a cross-platform React Native app for local grocery delivery, published "
                "to both the App Store and Play Store.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "iOS Engineer",
            "required_skills": ["Swift", "iOS SDK", "Xcode", "REST APIs", "App Store Deployment"],
            "preferred_skills": ["Kotlin", "Firebase", "Unit Testing"],
            "responsibilities": [
                "Build and maintain native iOS applications in Swift",
                "Integrate REST APIs and manage app state",
                "Own the App Store release and versioning process",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "",
        },
    },

    # =============================== MODERATE (50-69) ===============================
    {
        "id": "moderate_11_fullstack",
        "band": "moderate", "expected_min": 50, "expected_max": 69, "domain": "Full Stack",
        "resume": {
            "name": "Tyler Brooks",
            "skills": ["JavaScript", "React", "HTML", "CSS", "Firebase", "Git"],
            "education": ["B.S. in Information Technology, Arizona State University"],
            "experience": [
                "Frontend Developer (Intern), a small marketing agency (8 months): Built "
                "landing pages and simple client dashboards in React, using Firebase for "
                "basic auth and data storage. Limited backend work beyond Firebase functions."
            ],
            "projects": [
                "Built a personal budgeting app with a React frontend and Firebase backend "
                "for a class project.",
                "Built a to-do list app with local storage, no backend.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Full Stack Engineer",
            "required_skills": ["React", "Node.js", "PostgreSQL", "REST APIs", "Docker"],
            "preferred_skills": ["TypeScript", "AWS", "GraphQL"],
            "responsibilities": [
                "Build and maintain production backend services and APIs",
                "Design relational database schemas",
                "Own features end-to-end from frontend to database",
            ],
            "experience_level": "Mid-level (2-3 years)",
            "education_requirement": "Bachelor's degree in a technical field",
        },
    },
    {
        "id": "moderate_12_backend",
        "band": "moderate", "expected_min": 50, "expected_max": 69, "domain": "Backend",
        "resume": {
            "name": "Klaus Richter",
            "skills": ["Java", "Spring Boot", "MySQL", "Maven", "JUnit", "REST APIs",
                       "Object-Oriented Design"],
            "education": ["B.S. in Software Engineering, TU Munich"],
            "experience": [
                "Backend Developer, an enterprise logistics company (3 years): Built REST "
                "services in Java/Spring Boot backed by MySQL for a warehouse management "
                "system. Wrote unit and integration tests with JUnit. No exposure to Python "
                "or Django; some exposure to Docker for local development only."
            ],
            "projects": [
                "Built a small Spring Boot inventory-tracking service as a proof of concept.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Backend Engineer (Python)",
            "required_skills": ["Python", "Django", "PostgreSQL", "REST APIs", "Docker"],
            "preferred_skills": ["Celery", "AWS", "Kubernetes"],
            "responsibilities": [
                "Build and maintain Python/Django backend services",
                "Design PostgreSQL schemas and optimize queries",
                "Deploy services via Docker to production",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "Bachelor's degree in Computer Science or related field",
        },
    },
    {
        "id": "moderate_13_datascience",
        "band": "moderate", "expected_min": 50, "expected_max": 69, "domain": "Data Science",
        "resume": {
            "name": "Grace Adeyemi",
            "skills": ["Excel", "SQL", "Tableau", "PowerPoint", "Basic Python"],
            "education": ["B.Com in Business Analytics, University of Lagos"],
            "experience": [
                "Business Analyst, a retail chain (2 years): Built weekly sales dashboards in "
                "Tableau and Excel pivot tables. Wrote SQL queries to pull data for reporting. "
                "Took an online course in Python and pandas but has not used them in a "
                "production role."
            ],
            "projects": [
                "Completed a Kaggle tutorial project predicting housing prices using scikit-learn.",
            ],
            "certifications": ["Google Data Analytics Certificate"],
        },
        "jd": {
            "role": "Data Scientist",
            "required_skills": ["Python", "Machine Learning", "Statistics", "SQL",
                                 "scikit-learn"],
            "preferred_skills": ["A/B Testing", "XGBoost", "Deep Learning"],
            "responsibilities": [
                "Build and deploy predictive models to support product decisions",
                "Design and analyze A/B tests",
                "Communicate statistical findings to stakeholders",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "Bachelor's or Master's in a quantitative field",
        },
    },
    {
        "id": "moderate_14_genai",
        "band": "moderate", "expected_min": 50, "expected_max": 69, "domain": "Generative AI",
        "resume": {
            "name": "Ben Foster",
            "skills": ["Python", "Flask", "REST APIs", "JavaScript", "SQL"],
            "education": ["B.S. in Computer Science, University of Leeds"],
            "experience": [
                "Software Engineer, a general software consultancy (3 years): Built internal "
                "CRUD web tools in Flask for various clients. No dedicated AI/ML work in any "
                "professional role."
            ],
            "projects": [
                "Built a weekend hobby project that calls the OpenAI API to generate short "
                "story summaries, with minimal prompt iteration.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Generative AI Engineer",
            "required_skills": ["LLM APIs", "RAG", "Vector Databases", "Prompt Engineering",
                                 "Python"],
            "preferred_skills": ["LangChain", "Fine-tuning"],
            "responsibilities": [
                "Design and build production LLM-powered features",
                "Build and optimize RAG pipelines over large document sets",
                "Own prompt design and evaluation for reliability",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "",
        },
    },
    {
        "id": "moderate_15_cloud",
        "band": "moderate", "expected_min": 50, "expected_max": 69, "domain": "Cloud",
        "resume": {
            "name": "Victor Hallgren",
            "skills": ["Windows Server", "Active Directory", "Networking", "Bash",
                       "Basic AWS (EC2, S3)"],
            "education": ["Diploma in IT Infrastructure, Stockholm Technical College"],
            "experience": [
                "Systems Administrator, a mid-size manufacturing company (5 years): Managed "
                "on-premises Windows Server infrastructure, Active Directory, and internal "
                "networking. Migrated a handful of internal tools to basic EC2/S3 setups but "
                "no cloud-native architecture experience (no IaC, no containers, no Kubernetes)."
            ],
            "projects": [],
            "certifications": ["CompTIA Network+"],
        },
        "jd": {
            "role": "Cloud Engineer",
            "required_skills": ["AWS", "Terraform", "Kubernetes", "CI/CD", "Python"],
            "preferred_skills": ["Docker", "Monitoring", "Cost Optimization"],
            "responsibilities": [
                "Design and provision cloud infrastructure as code",
                "Manage containerized workloads on Kubernetes",
                "Build CI/CD pipelines for infrastructure changes",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "",
        },
    },

    # ================================== WEAK (20-49) ==================================
    {
        "id": "weak_16_ml",
        "band": "weak", "expected_min": 20, "expected_max": 49, "domain": "Machine Learning",
        "resume": {
            "name": "Oliver Bennett",
            "skills": ["HTML", "CSS", "JavaScript", "WordPress", "PHP"],
            "education": ["B.A. in Communications, University of Leicester"],
            "experience": [
                "Web Developer, a small marketing agency (2 years): Built WordPress and PHP "
                "sites for small business clients. Once used a no-code AI writing tool "
                "(Jasper) to help draft blog post copy for a client, with no technical "
                "involvement in how the tool worked."
            ],
            "projects": [
                "Built a handful of WordPress brochure sites for local businesses.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Machine Learning Engineer",
            "required_skills": ["Python", "PyTorch", "Model Training", "Statistics",
                                 "Linear Algebra"],
            "preferred_skills": ["Computer Vision", "MLOps"],
            "responsibilities": [
                "Design, train, and evaluate ML models from scratch",
                "Deploy models to production inference pipelines",
                "Collaborate with research on new modeling approaches",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "Master's degree in ML, CS, or related quantitative field",
        },
    },
    {
        "id": "weak_17_devops",
        "band": "weak", "expected_min": 20, "expected_max": 49, "domain": "DevOps",
        "resume": {
            "name": "Michelle Tan",
            "skills": ["Manual Testing", "Test Case Design", "Jira", "Basic SQL",
                       "Excel"],
            "education": ["B.S. in Information Technology, Nanyang Polytechnic"],
            "experience": [
                "QA Analyst, an e-commerce company (3 years): Wrote and executed manual test "
                "cases for web checkout flows, logged bugs in Jira. Occasionally wrote simple "
                "SQL queries to verify data during testing. No scripting/automation, no "
                "infrastructure, no cloud experience."
            ],
            "projects": [],
            "certifications": ["ISTQB Foundation Level"],
        },
        "jd": {
            "role": "Senior DevOps / SRE Engineer",
            "required_skills": ["Kubernetes", "Docker", "Terraform", "AWS", "Python",
                                 "CI/CD"],
            "preferred_skills": ["Prometheus", "Incident Response", "Go"],
            "responsibilities": [
                "Own production infrastructure reliability and incident response",
                "Build and maintain Kubernetes-based deployment pipelines",
                "Automate infrastructure provisioning with Terraform",
            ],
            "experience_level": "Senior (5+ years)",
            "education_requirement": "",
        },
    },
    {
        "id": "weak_18_frontend",
        "band": "weak", "expected_min": 20, "expected_max": 49, "domain": "Frontend",
        "resume": {
            "name": "Ahmed Siddiqui",
            "skills": ["Python", "Django", "PostgreSQL", "REST APIs", "Docker", "AWS"],
            "education": ["B.S. in Computer Science, LUMS"],
            "experience": [
                "Backend Engineer, a payments startup (4 years): Built Django REST services "
                "and PostgreSQL data models for a payments platform. Has never built a "
                "frontend UI professionally; all frontend work in his career was done by a "
                "separate team."
            ],
            "projects": [
                "Built backend APIs for several internal admin tools consumed by a frontend "
                "team he did not work on.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Senior Frontend Engineer",
            "required_skills": ["React", "TypeScript", "CSS", "Accessibility",
                                 "Frontend Performance Optimization"],
            "preferred_skills": ["Next.js", "Design Systems"],
            "responsibilities": [
                "Build and own complex, accessible UI components",
                "Optimize frontend performance and bundle size",
                "Partner with design on interaction and visual polish",
            ],
            "experience_level": "Senior (4+ years)",
            "education_requirement": "",
        },
    },
    {
        "id": "weak_19_promptengineering",
        "band": "weak", "expected_min": 20, "expected_max": 49, "domain": "Prompt Engineering",
        "resume": {
            "name": "Laura Bianchi",
            "skills": ["Copywriting", "SEO Writing", "Content Strategy", "WordPress CMS",
                       "Basic ChatGPT usage"],
            "education": ["B.A. in English Literature, University of Bologna"],
            "experience": [
                "Content Writer, a marketing agency (3 years): Wrote blog posts, SEO copy, "
                "and social media content. Uses ChatGPT informally as a writing aid, but has "
                "no programming background and has never built or evaluated an AI system."
            ],
            "projects": [],
            "certifications": [],
        },
        "jd": {
            "role": "Prompt Engineer",
            "required_skills": ["Python", "Prompt Engineering", "LLM Evaluation",
                                 "API Integration", "JSON"],
            "preferred_skills": ["Fine-tuning", "LangChain"],
            "responsibilities": [
                "Design and programmatically test prompts across LLM providers",
                "Build evaluation scripts to measure output quality",
                "Integrate prompt pipelines into product APIs",
            ],
            "experience_level": "Mid-level (2+ years)",
            "education_requirement": "",
        },
    },
    {
        "id": "weak_20_mobile",
        "band": "weak", "expected_min": 20, "expected_max": 49, "domain": "Mobile Development",
        "resume": {
            "name": "Ivy Zhang",
            "skills": ["SQL", "Excel", "Tableau", "Power BI", "Statistics"],
            "education": ["B.S. in Economics, National University of Singapore"],
            "experience": [
                "Data Analyst, a retail bank (2 years): Built reporting dashboards in Tableau "
                "and Power BI, wrote SQL queries for ad-hoc analysis. No mobile development, "
                "no programming beyond SQL and basic Excel macros."
            ],
            "projects": [],
            "certifications": [],
        },
        "jd": {
            "role": "Android Engineer",
            "required_skills": ["Kotlin", "Android SDK", "Jetpack Compose", "REST APIs",
                                 "Android Studio"],
            "preferred_skills": ["Firebase", "Unit Testing"],
            "responsibilities": [
                "Build and maintain native Android applications in Kotlin",
                "Implement UI with Jetpack Compose",
                "Integrate REST APIs and manage local persistence",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "",
        },
    },

    # ================================ VERY POOR (0-19) ================================
    {
        "id": "verypoor_21_backend",
        "band": "very_poor", "expected_min": 0, "expected_max": 19, "domain": "Backend",
        "resume": {
            "name": "Nadia Petrova",
            "skills": ["Adobe Photoshop", "Adobe Illustrator", "Branding", "Typography",
                       "Client Presentations"],
            "education": ["B.F.A. in Graphic Design, Rhode Island School of Design"],
            "experience": [
                "Graphic Designer, a branding studio (5 years): Designed logos, brand "
                "identities, and marketing collateral for clients using Adobe Creative Suite. "
                "No programming, software engineering, or technical background of any kind."
            ],
            "projects": [
                "Designed a full brand identity package (logo, color system, typography) for "
                "a local coffee chain.",
            ],
            "certifications": [],
        },
        "jd": {
            "role": "Backend Software Engineer",
            "required_skills": ["Python", "Django", "PostgreSQL", "REST APIs",
                                 "Distributed Systems"],
            "preferred_skills": ["Docker", "Kubernetes", "AWS"],
            "responsibilities": [
                "Design and build scalable backend services",
                "Own database schema design and query optimization",
                "Participate in on-call rotation for production systems",
            ],
            "experience_level": "Mid-Senior (3+ years)",
            "education_requirement": "Bachelor's degree in Computer Science or equivalent",
        },
    },
    {
        "id": "verypoor_22_cloud",
        "band": "very_poor", "expected_min": 0, "expected_max": 19, "domain": "Cloud",
        "resume": {
            "name": "Carlos Jimenez",
            "skills": ["Guest Relations", "POS Systems", "Staff Scheduling", "Inventory Ordering"],
            "education": ["Diploma in Hospitality Management, Cornell School of Hotel Administration"],
            "experience": [
                "Restaurant Manager, a hotel chain (6 years): Managed daily restaurant "
                "operations, staff scheduling, and vendor relationships. Used a point-of-sale "
                "system and basic inventory software. No technical or IT background."
            ],
            "projects": [],
            "certifications": ["ServSafe Manager Certification"],
        },
        "jd": {
            "role": "Cloud Infrastructure Engineer",
            "required_skills": ["AWS", "Terraform", "Kubernetes", "Networking", "Python"],
            "preferred_skills": ["GCP", "Monitoring"],
            "responsibilities": [
                "Design and provision cloud infrastructure",
                "Manage Kubernetes clusters and networking",
                "Automate infrastructure with Terraform",
            ],
            "experience_level": "Mid-level (2-4 years)",
            "education_requirement": "",
        },
    },
    {
        "id": "verypoor_23_genai",
        "band": "very_poor", "expected_min": 0, "expected_max": 19, "domain": "Generative AI",
        "resume": {
            "name": "Helen Marsh",
            "skills": ["QuickBooks", "Tax Preparation", "Bookkeeping", "Excel",
                       "Financial Reporting"],
            "education": ["B.Com in Accounting, University of Manchester"],
            "experience": [
                "Staff Accountant, a mid-size accounting firm (7 years): Prepared tax filings "
                "and financial statements for small business clients using QuickBooks and "
                "Excel. No programming or AI/ML background."
            ],
            "projects": [],
            "certifications": ["Chartered Accountant (ACA)"],
        },
        "jd": {
            "role": "Generative AI Research Engineer",
            "required_skills": ["Python", "PyTorch", "Transformer Architectures",
                                 "LLM Pretraining", "Distributed Training"],
            "preferred_skills": ["CUDA", "Research Publications"],
            "responsibilities": [
                "Research and implement novel transformer architectures",
                "Run large-scale distributed model training experiments",
                "Publish and present findings internally and externally",
            ],
            "experience_level": "Senior (5+ years) / PhD preferred",
            "education_requirement": "PhD or Master's in Machine Learning, CS, or related field",
        },
    },
    {
        "id": "verypoor_24_fullstack",
        "band": "very_poor", "expected_min": 0, "expected_max": 19, "domain": "Full Stack",
        "resume": {
            "name": "Susan Whitfield",
            "skills": ["Curriculum Design", "Classroom Management", "Lab Safety",
                       "Google Classroom", "Grading Rubrics"],
            "education": ["M.Ed. in Science Education, Boston College"],
            "experience": [
                "High School Biology Teacher, a public school district (10 years): Designed "
                "curriculum, led laboratory sessions, and managed classrooms of 30+ students. "
                "Used Google Classroom for assignments. No software development experience."
            ],
            "projects": [],
            "certifications": ["State Teaching License, Biology 9-12"],
        },
        "jd": {
            "role": "Senior Full Stack Software Engineer",
            "required_skills": ["React", "Node.js", "TypeScript", "PostgreSQL",
                                 "System Design"],
            "preferred_skills": ["AWS", "GraphQL", "Docker"],
            "responsibilities": [
                "Design and build full-stack features end to end",
                "Participate in system design and architecture discussions",
                "Mentor junior engineers",
            ],
            "experience_level": "Senior (5+ years)",
            "education_requirement": "Bachelor's degree in Computer Science or equivalent",
        },
    },
    {
        "id": "verypoor_25_devops",
        "band": "very_poor", "expected_min": 0, "expected_max": 19, "domain": "DevOps",
        "resume": {
            "name": "Derek Simmons",
            "skills": ["Salesforce CRM", "Cold Calling", "Quota Attainment",
                       "Sales Presentations", "Negotiation"],
            "education": ["B.A. in Business Administration, University of Alabama"],
            "experience": [
                "Account Executive, a B2B software company (5 years): Managed a book of "
                "enterprise accounts, ran the full sales cycle from prospecting to close using "
                "Salesforce CRM. Consistently exceeded quota. No technical or engineering "
                "background."
            ],
            "projects": [],
            "certifications": [],
        },
        "jd": {
            "role": "DevOps / Site Reliability Engineer",
            "required_skills": ["Kubernetes", "Docker", "Terraform", "Linux", "Python",
                                 "CI/CD"],
            "preferred_skills": ["Go", "Monitoring", "Incident Response"],
            "responsibilities": [
                "Own production infrastructure and reliability",
                "Automate deployments and infrastructure provisioning",
                "Lead incident response and postmortems",
            ],
            "experience_level": "Mid-Senior (3+ years)",
            "education_requirement": "",
        },
    },
]

if __name__ == "__main__":
    from collections import Counter
    print(f"Total pairs: {len(BENCHMARK)}")
    print("By band:", Counter(p["band"] for p in BENCHMARK))
    print("By domain:", Counter(p["domain"] for p in BENCHMARK))
