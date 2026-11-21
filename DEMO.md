# 3-Minute Interview Walkthrough & Live Demonstration Script
### Project: AI-Based Resume Matching & Candidate Ranking System

---

### Step 1: The Problem & Vision (0:00 – 0:45)
- **What to say**:
  > *"Traditional Applicant Tracking Systems (ATS) suffer from a critical flaw: they rely on naive keyword counting. An unqualified candidate who pastes 50 keywords in white text easily ranks at the top. On the other hand, relying on closed-source cloud LLM APIs creates hallucinations, non-deterministic score drift, high API costs, and serious privacy/GDPR compliance risks.
  > 
  > I built this **AI-Based Resume Matching & Candidate Ranking System** to solve this. It is a 100% deterministic, explainable resume matching engine that runs completely locally without external API dependencies. Every point awarded is backed by auditable evidence."*

---

### Step 2: Recruiter Ingestion & Batch Upload Flow (0:45 – 1:30)
- **What to do**:
  1. Open `http://localhost:5173`.
  2. Paste a Job Description or upload a document (`.txt`, `.pdf`, `.docx`).
  3. Click **"Extract Key Requirements"**.
  4. **Highlight the Requirement Review chip editor**:
     > *"Notice that the system parsed the unstructured JD into structured must-have skills, preferred nice-to-have skills, required years, and minimum degree level. As a recruiter, I can interactively add or remove requirements, or define interchangeable 'Any-Of' groups before locking them in."*
  5. Click **"Save & Proceed to Resume Upload"**.
  6. Drag and drop candidate resumes (`.pdf` or `.docx`) into the upload dropzone.
  7. Point to the concurrent progress rows:
     > *"The engine parses PDF and DOCX files in parallel using PyMuPDF and python-docx, extracting employment timelines, section boundaries, and candidate contacts."*
  8. Click **"Run Matching"**.

---

### Step 3: Candidate Ranking & Deep Dive (1:30 – 2:15)
- **What to do**:
  1. Show the **Candidate Ranking Dashboard**:
     - Explain the top summary cards: Total Candidates, Average Score, Top Candidate, and Processing Time.
     - Toggle the **"Anonymize Profiles"** switch:
       > *"With one toggle, candidate names become 'Candidate N' and contact details are masked, removing unconscious demographic bias before first-round screening."*
     - Demonstrate the **Min Match Score Slider** and click **Export CSV**.
  2. Click on the top candidate to open their **Candidate Detail Page**:
     - **Score Hero**: Point to the circular score gauge.
     - **Waterfall Chart**:
       > *"Every point is mathematically accounted for in this additive waterfall chart: Skills Match (+32 pts), Semantic Alignment (+21 pts), Experience Relevance (+22 pts), and Education (+10 pts)."*
     - **Skill Evidence Badges**:
       > *"We don't just check if a skill was mentioned; we tag evidence. A skill demonstrated inside employment bullets receives full credit (1.0), whereas a skill found only in a buzzword list receives discounted credit (0.6)."*
     - **Semantic Fallback**: Point to partial skill matches with cosine similarity.
     - **Experience Comparison**: Show the bar comparing Relevant Years vs. Required Years vs. Total Career Years.
     - **Plain-English Reasons**: Read the generated rationale bullets and tailored interview questions.
  3. Click the **Keyword-Stuffed Candidate**:
     > *"Notice how the keyword-stuffed resume was penalized down to the bottom tier. Because it lacked workplace bullet evidence and relevant career duration, our core-skills safety gate capped it at 65."*

---

### Step 4: Technical Architecture & Interview Defense (2:15 – 3:00)
- **Key points to highlight**:
  1. **Stack**: FastAPI (Python 3.12) backend + React 18 / TypeScript / Tailwind CSS frontend + SQLite / PostgreSQL.
  2. **Sentence-level Max-Similarity**:
     > *"Mean-pooling a 2-page resume into a single vector averages out specific accomplishments into an uninformative centroid. We compute sentence-level Max-Similarity: comparing each required job responsibility directly against individual candidate achievement bullets."*
  3. **Local ONNX Execution**:
     > *"We bundle `BAAI/bge-small-en-v1.5` using FastEmbed offline. Total backend bundle is ~345 MB. Zero per-query API costs, zero rate limits, sub-second latency, and complete privacy compliance."*
  4. **Empirical Benchmarks**:
     > *"Validated across 30 synthetic corner-cases and 2,484 real-world PDF resumes:
     > - 99.96% parse success rate.
     > - 0.24 years Mean Absolute Error on multi-interval career dates.
     > - Full hybrid model achieved a Spearman correlation of 0.953 and NDCG@5 of 1.000."*
  5. **Advanced NLP Traps Defended**:
     > *"We engineered defenses against real-world resume traps:
     > - **Negation Detection**: If someone writes 'I have no experience with Kubernetes' or 'never worked with AWS', naive matchers award points. Our SkillMatcher inspects the preceding clause for negation operators and awards zero credit.
     > - **'Any-Of' Skill Grouping**: When a JD asks for 'Java or Kotlin', the system groups them into an interchangeable set where having either satisfies the must-have requirement with full credit."*
