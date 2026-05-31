# Contributing to DevOps Incident Agent

We love your input! We want to make contributing to this project as easy and transparent as possible.

## Development Setup

1. Make sure you have Python 3.11+, Node.js 18+, and PostgreSQL 15+ installed.
2. Clone the repository and copy `.env.example` to `.env`.
3. Start the database using Docker:
   ```bash
   docker-compose up -d db
   ```
4. Setup backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```
5. Setup frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Adding a New Agent to the Pipeline

If you want to add a new step to the LangGraph pipeline (e.g., an agent that checks AWS status):

1. Create a new file in `backend/agents/`, e.g., `aws_status_agent.py`.
2. Follow the structure of existing agents:
   - Always return a dictionary matching a TypedDict.
   - Wrap the LLM call in a `try/except` block and return safe defaults on failure.
   - Include at least 2 few-shot examples in the system prompt.
3. Update `IncidentState` in `backend/agents/graph.py` with your agent's output keys.
4. Add your node function to `backend/agents/graph.py` and insert it into the pipeline flow in `run_incident_pipeline`.
5. Update `models/incident.py` if you want to persist the output to the database.

## Adding a Notification Channel

To integrate with a new service (e.g., Slack):

1. Create a new file in `backend/services/`, e.g., `slack_service.py`.
2. Implement an async function like `send_slack_alert(incident_data: dict)`.
3. Add configuration keys to `backend/config.py` (e.g., `SLACK_WEBHOOK_URL`).
4. Update `node_response_orchestrator` in `backend/agents/response_orchestrator.py` to call your new service in a separate `try/except` block.

## Pull Requests

- Keep PRs focused on a single feature or bugfix.
- Ensure all tests pass (if applicable) and your code is properly formatted.
- Write a clear PR description detailing what changed.
