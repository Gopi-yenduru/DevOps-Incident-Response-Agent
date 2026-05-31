# DevOps Incident Agent 🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Stars](https://img.shields.io/github/stars/owner/devops-incident-agent?style=social)](https://github.com/owner/devops-incident-agent)
[![Made with LangGraph](https://img.shields.io/badge/Made_with-LangGraph-orange.svg)](https://python.langchain.com/docs/langgraph)

A production-grade Autonomous DevOps Incident Response Agent. Monitors applications in real-time, leverages a 5-agent LangGraph AI pipeline to diagnose root causes, and automatically orchestrates responses (GitHub Issues, PRs, and Telegram alerts).

![Agent Demo](https://via.placeholder.com/800x400.png?text=Demo+GIF+Placeholder)

## ✨ Features

- **5-Agent AI Pipeline:** Powered by LangGraph and Google Gemini 2.0.
  - *Anomaly Detector:* Identifies true errors vs noise.
  - *Incident Correlator:* Groups related incidents.
  - *Root Cause Analyzer:* Performs deep causal reasoning.
  - *Fix Suggestion Agent:* Recommends actionable fixes and code snippets.
  - *Response Orchestrator:* Dispatches to GitHub and Telegram.
- **Incident Correlation Engine:** Reduces alert fatigue by grouping related logs.
- **Auto-Resolution:** Automatically marks incidents as resolved if no recurrence happens in a configurable window.
- **Real-Time Dashboard:** React frontend displaying live incidents, MTTR trends, and agent accuracy.
- **Webhook Integration:** Easily push logs from any app using HMAC-SHA256 secured webhooks.
- **Built-in Log Simulator:** Test and demo the system with realistic mock logs.

## 📊 Real-World Impact (Case Study)

*In 30 days of monitoring 3 apps:*
- **X** incidents detected
- **Y%** root cause accuracy
- Avg MTTR reduced from **Z** to **W** minutes

*(Metrics to be populated after production deployment)*

## 🚀 Quick Start

1. **Clone the repo:**
   ```bash
   git clone https://github.com/owner/devops-incident-agent.git
   cd devops-incident-agent
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your GEMINI_API_KEY, GITHUB_TOKEN, TELEGRAM_BOT_TOKEN
   ```

3. **Start the stack:**
   ```bash
   docker-compose up -d
   ```

4. **Access the Dashboard:**
   Open `http://localhost:3000` in your browser.

## 🔌 Webhook Integration

To monitor your own application, send a POST request to the webhook endpoint.

1. Register your app in the Dashboard to get a `webhook_secret`.
2. Compute the HMAC-SHA256 signature of the JSON payload.
3. Send the logs:

```bash
curl -X POST http://localhost:8000/api/v1/logs/webhook/<APP_ID> \
     -H "Content-Type: application/json" \
     -H "X-Signature: sha256=<HMAC_HEX>" \
     -d '{"logs": ["ERROR: Connection timeout in auth-service"]}'
```

## 🏗️ Architecture

```text
Log Stream ──> [ FastAPI ] ──> [ DB ]
                   │
                   ▼
         ┌───────────────────┐
         │ LangGraph Pipeline│
         │ 1. Anomaly Detect │
         │ 2. Correlate      │
         │ 3. Root Cause     │
         │ 4. Suggest Fix    │
         │ 5. Orchestrate    │
         └─────────┬─────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
    [ GitHub ]          [ Telegram ]
```

## 🗺️ Roadmap

- [ ] Slack & PagerDuty Integrations
- [ ] Multi-tenant support
- [ ] Auto-scaling suggestions agent
- [ ] Support for local open-source LLMs (Llama 3 / Mistral)

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to run the project locally and add new agents to the pipeline.

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
