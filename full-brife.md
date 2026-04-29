the new project idea :
[4/29/2026 6:40 AM] yousef: ￼ (https://app.code-quests.com/)
Notes (https://app.code-quests.com/quest-view/79)
Alerts (https://app.code-quests.com/quest-view/79)
Chat (https://app.code-quests.com/quest-view/79)
Chat List
Show All
A
￼
Archie Parker
Kalid is online
￼
Alfie Mason
Taherah left 7 mins ago
￼
AharlieKane
Sami is online
￼
Athan Jacoby
Nargis left 30 mins ago
B
￼
Bashid Samim
Rashid left 50 mins ago
￼
Breddie Ronan
Kalid is online
￼
Ceorge Carson
Taherah left 7 mins ago
D
￼
Darry Parker
Sami is online
￼
Denry Hunter
Nargis left 30 mins ago
J
￼
Jack Ronan
Rashid left 50 mins ago
￼
Jacob Tucker
Kalid is online
￼
James Logan
Taherah left 7 mins ago
￼
Joshua Weston
Sami is online
O
￼
Oliver Acker
Nargis left 30 mins ago
￼
Oscar Weston
Rashid left 50 mins ago
￼
yousefal...contestant
Quests (https://app.code-quests.com/quest-view/79)
Overview
📅 Register before:
Thursday, April 30th
🕙 Submit before:
Sunday, May 3th
Registration Opened
📈 Challenge Statistics
🙋‍♀️Registrations: 30
📦 Submissions: 1
🗒️ Challenge Details
💪🏼 Difficulty: Intermediate
💼 Hiring Quest – Core Software Engineer (Fullstack + AI) @ FinTech Company
Description
We are a FinTech company serving one of Egypt's major e-commerce platforms. As we enter our next phase of growth, we are building a core in-house engineering team to drive technology forward - and this role is at the heart of it.
We’re hiring a Core Software Engineer (Founding Engineer) (1–3 YOE) to help us build this system from the ground up.
🕓 Start Date: Immediate
🌍 Location: The City Center New Cairo, Egypt (On-site)
💰 Salary: Starting From 25 K EGP
🛠️ How the Hiring Quest Works
1️⃣ Register 
2️⃣ Submit your solution before the deadline
3️⃣ Submissions are reviewed and all candidates receive feedback
4️⃣ Top candidates join a technical review session to walk through their submitted task
5️⃣ Qualified candidates are recommended to the hiring company for next steps
👉 The technical session focuses on your thinking and understanding of your solution, so use AI as a support tool only — not a replacement for your own work.
🔍 Who We’re Looking For
✅ 1–3 years of full-stack experience (Node.js or Python + React / Next.js)
✅ Strong backend + system design fundamentals
✅ Experience building APIs and working with databases
✅ Comfortable integrating AI/LLMs into products
✅ Has shipped real projects end-to-end
💡 Bonus:
Vector databases (Pinecone, Chroma, FAISS)
Background jobs / queues
Search systems / retrieval pipelines
DevOps / Docker
🧠 Mindset:
Builder mindset (you create, not just implement)
High ownership & curiosity
Strong problem-solving and communication
🎯 Your Mission: “AI Knowledge Operations System”
🧠 Business Context
Modern teams are drowning in information:
Docs in Notion / Google Drive
Conversations in Slack
Data in dashboards
Decisions lost in meetings
Your mission is to build a system that:
👉 Ingests knowledge from multiple sources
👉 Structures it into searchable intelligence
👉 Allows users to ask questions and get accurate, contextual answers
👉 Surfaces insights proactively (not just reactively)
📌 The Challenge
1️⃣ Step 1 – Multi-Source Knowledge Ingestion (Backend)
Build a system that:
Accepts multiple data sources:
.pdf, .txt, .md
(Bonus: simulated Slack / Notion data as JSON)
Processes:
Text extraction
Chunking
Embedding generation
Stores:
Documents + metadata
Embeddings in a vector DB
Endpoints:
POST /api/ingest/files
POST /api/ingest/source (simulate external data)
GET /api/docs
GET /api/docs/:id
💡 Bonus:
Background ingestion jobs
Deduplication
Versioning documents
2️⃣ Step 2 – Retrieval + Reasoning Engine (Core AI)
Build a retrieval-augmented AI system:
Endpoint:
POST /api/ai/query
Input:
{
  "question": "What decisions were made about product pricing last week?"
}
System should:
Retrieve relevant chunks (semantic search)
Rank / filter results
Use LLM to:
Answer the question
Cite sources
Handle ambiguity
Output:
{
  "answer": "...",
  "sources": [...],
  "confidence": 0.91,
  "reasoning": "optional but bonus"
[4/29/2026 6:40 AM] yousef: }
💡 Bonus:
Multi-step retrieval (query rewriting, re-ranking)
Hybrid search (keyword + vector)
Prompt engineering layers
3️⃣ Step 3 – AI Copilot Interface (Frontend)
Build a knowledge assistant UI, not just a chatbot.
Features:
Upload & manage documents
View processed knowledge base
Ask questions in chat interface
See:
Answers
Sources
Context snippets
UX Expectations:
Clean, intuitive UI
Fast responses
Thoughtful interaction design
Tech:
Next.js (App Router)
TailwindCSS
React Query / SWR
💡 Bonus:
Streaming responses
Source preview panel
Search + filters
4️⃣ Step 4 – Proactive Intelligence Layer (Advanced)
Move beyond Q&A → AI that suggests insights
Build a system that:
Periodically scans knowledge base
Generates insights like:
“Frequent issues mentioned in support logs”
“Repeated decisions across teams”
“Conflicting information detected”
Endpoint:
GET /api/ai/insights
💡 Bonus:
Scheduled jobs
Insight categorization
Notifications (mocked)
5️⃣ Step 5 – System Design & Infrastructure
Design like a real product:
Dockerized setup
Modular architecture
Logging & error handling
💡 Bonus:
Separate services (API / worker / AI service)
Caching layer
Rate limiting
🗄️ Suggested Tech Stack
Backend: FastAPI / Node.js
Frontend: Next.js
Database: PostgreSQL
Vector DB: Chroma / FAISS / Pinecone
AI: OpenAI API
Infra: Docker Compose
🧩 Example Flow
User uploads documents → system processes + embeds
User asks question → retrieval + LLM reasoning
System returns answer + sources
Background job generates insights → shown in dashboard
🎁 Bonus Points
✨ Advanced retrieval pipeline
✨ Insight generation (proactive AI)
✨ Clean system architecture
✨ Strong UX thinking
✨ Performance optimization
✨ Observability