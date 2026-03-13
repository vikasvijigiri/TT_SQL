# 🌐 nQuire: Agentic AI Business Intelligence

nQuire is a premium, ChatGPT-style web application that transforms natural language questions into professional data insights. Built with a high-performance multi-agent Text-to-SQL engine, it provides instant SQL generation, execution results, and token-wise streaming business insights.

---

## 🏗️ Architecture Overview

- **Frontend**: React (Vite) + Vanilla CSS (Glassmorphism & Professional Animations).
- **Backend**: FastAPI + Modular Layered Architecture (Controllers, Models, Repositories, Services).
- **Vector Store**: Qdrant (for Column-Level RAG).
- **Database**: PostgreSQL (Amazon RDS) or SQLite.

---

## 🚀 End-to-End Setup Guide

Follow these steps to get the entire application running from scratch.

### 1. Repository & Environment
```bash
git clone https://github.com/NG-VikasV/TT_SQL.git
cd TT_SQL
```

### 2. Backend Initialization
```bash
cd backend
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Initialization
```bash
cd ../frontend
npm install
cd ..
```

### 4. Configuration (`.env`)
Create a `.env` file in the **backend** directory:
```ini
# LLM Provider (Direct or Proxy)
LLM_MODEL=bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-1

# Qdrant Vector DB
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=xxx

# Database (PostgreSQL)
RDS_HOST=xxx
RDS_PORT=5432
RDS_DATABASE=xxx
RDS_USER=xxx
RDS_PASSWORD=xxx
DB_TYPE=postgres
```

### 5. Data Retrieval Preparation (RAG)
Run these commands to ingest your database schema into the vector store.
```bash
# 1. Extract and Enrich Metadata
python backend/app/repositories/rag/extract_metadata.py --instance-id setup --enrich

# 2. Populate Vector Store
python backend/app/repositories/scripts/populate_vector_store.py
```

---

## 🏃 Launching the Application

You need to run two separate processes:

### Terminal 1: Backend (FastAPI)
```bash
# From backend directory
python main.py
```
*Backend runs at `http://localhost:8000`*

### Terminal 2: Frontend (Vite)
```bash
# From frontend directory
npm run dev
```
*Frontend runs at `http://localhost:5173`*

---

## 📊 Key Features & Usage

1. **Natural Language Querying**: Ask questions like *"What is the OTIF loss breakdown by reason code?"*
2. **Thinking States**: The UI shows real-time pulse updates for each agent (Planning, Building, Executing).
3. **Turbo Streaming**: achievements sub-2s TTFT by parallelizing business narratives with technical discovery.
4. **Professional Results**: View generated SQL and interactive data tables directly in the chat bubbles.

---

## 📂 Project Structure
```text
TT_SQL/
├── backend/                  # Python Agentic Engine & API
│   ├── app/
│   │   ├── controllers/      # API Routes
│   │   ├── models/           # Schemas & Paths
│   │   ├── repositories/     # Data & Scripts
│   │   └── services/         # Agents & Logic
│   └── main.py               # FastAPI Entry point
├── frontend/                 # React Application
│   ├── src/App.jsx           # Main Chat Interface
│   └── src/components/       # UI Components
└── README.md                 # Project Overview
```
