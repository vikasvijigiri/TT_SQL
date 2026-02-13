# TT_SQL: nQuiry Text2SQL Agent

nQuiry is an industry-grade Text-to-SQL engine that converts natural language questions into executable SQL queries with high precision. It uses a multi-agent architecture to plan, generate, criticize, and refine SQL queries iteratively.

## ✨ Key Features

- **Multi-Agent Pipeline**: Planner, Generator, Critic, and Refiner agents work together.
- **Self-Correction**: Automatically detects and fixes SQL errors by reading SQLite error messages.
- **RAG-Augmented**: Uses vector search (Qdrant) or Amazon Bedrock Knowledge Bases to inject domain knowledge.
- **Interactive UI**: A polished Streamlit dashboard with a conversational narrator.
- **Safe & Secure**: Only executes `SELECT` statements (by design intent, though requires DB permissions).

---

## 🚀 Building from Scratch

Follow these steps to set up the project on your local machine.

### 1. Prerequisites
- **Python 3.10+** installed.
- **Git** installed.
- An API Key for either **OpenAI** (GPT-4) or **AWS Bedrock** (Claude 3.5 Sonnet).

### 2. Clone the Repository
```bash
git clone <repository-url>
cd txt2sql-Nakul
```

### 3. Set Up Virtual Environment (Recommended)
Create an isolated Python environment to keep dependencies clean.

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
Install all required packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration (.env)

You must create a `.env` file in the root directory. This file holds your API keys and configuration secrets.

**Create a file named `.env` and add the following:**

### 🔒 Mandatory Variables
You need at least one LLM provider configured.

**Option A: Using OpenAI (GPT-4o)**
```ini
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4o
```

**Option B: Using AWS Bedrock (Claude 3.5 Sonnet)**
```ini
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_DEFAULT_REGION=us-east-1
LLM_MODEL=bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
```
*(Note: Ensure your AWS user has Bedrock Full Access permissions)*

### 🔓 Optional Variables (RAG & Advanced)

**Qdrant (Local Vector Store)**
Used for storing successful query examples for few-shot learning.
```ini
# Defaults to local memory if not set, but recommended for persistence
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key-if-cloud-hosted
```

**Amazon Bedrock Knowledge Base**
If you want to use AWS's managed RAG solution.
```ini
BEDROCK_KB_ID=your-knowledge-base-id
```

**Model Fallbacks**
Override specific agents to use different models (Optional).
```ini
PLANNER_MODEL=gpt-4o
GENERATOR_MODEL=gpt-4o
```

---

## 🧠 RAG Implementation Details

nQuiry uses **Retrieval-Augmented Generation (RAG)** to improve accuracy by finding similar past questions.

### How it Works
1.  **Vector Store**: The system maintains a database of `(Natural Question, Correct SQL)` pairs.
2.  **Retrieval**: When you ask a new question, the system searches the vector store for the top 3-5 most semantically similar past questions.
3.  **Context Injection**: These examples are injected into the Prompt as "Few-Shot Examples".
4.  **Learning**: When a query is successfully executed and verified (score=100%), it can be automatically upserted back into the vector store, making the system smarter over time.

### Supported Backends
1.  **Qdrant**: Best for local development or custom Docker deployment.
2.  **Amazon Bedrock Knowledge Base**: Managed AWS solution for enterprise scale.

---

## 🏃‍♂️ Running the Application

Once installed and configured:

1.  **Start the UI**:
    ```bash
    streamlit run src/app_ui.py
    ```

2.  **Use the Dashboard**:
    - Select a Task ID (from `spider2-lite.jsonl`) or type your own question.
    - Click **Run Pipeline**.
    - Watch the **Narrator** explain the steps.
    - Interact with the **"Show Chart"** button to see visualizations.

---

## 📂 Project Structure

```text
TT_SQL/
├── results/               # Generated SQL, CSVs, and logs
├── src/
│   ├── app_ui.py          # Main Streamlit Dashboard
│   ├── tt_sql/            # Core Package (Ranked as TT_SQL)
│       ├── agents/        # Planner, Generator, Narrator Agents
│       ├── core/          # Orchestrator, LLM Service, State Management
│       ├── prompts/       # YAML Prompt Templates (Easy to edit)
├── requirements.txt       # Python Dependencies
├── .env                   # API Keys (GitIgnored)
└── README.md              # Documentation
```
