# Incident Response Agent

An AI-assisted incident response system for local microservices.

The project connects application telemetry, alerts, logs, and LLM analysis into one incident workflow. Instead of making an on-call engineer jump between Prometheus, Loki, service logs, and source code, the agent gathers the first layer of context automatically and produces a structured incident summary.

**Demo:** [YouTube](https://www.youtube.com/watch?v=KXLgdUAnoSU&t=2s) &nbsp;|&nbsp; **DevPost:** [devpost.com/software/incident-responce-agent](https://devpost.com/software/incident-responce-agent)

---

## Inspiration

Production outages are stressful because the answer is rarely in one place. Metrics live in Prometheus, logs live in another system, deployment context may be in Git, and the on-call engineer still has to connect the dots under pressure.

This project was built around one question:

> What if the first pass of incident triage could be automated before someone opens five dashboards and starts grepping logs?

The goal is not to replace engineers. The goal is to give them a useful first draft: what fired, what changed, what evidence exists, what probably caused it, and what to check next.

---

## What It Does

Incident Response Agent monitors demo services and reacts when Prometheus detects an incident.

When something goes wrong — service downtime, MongoDB dependency failure, or rising 5xx errors:

1. Prometheus evaluates alert rules.
2. Alertmanager sends a webhook to `incident-agent-workflow`.
3. The agent queries Prometheus for live metrics.
4. The agent queries Loki for recent logs from the affected service.
5. A 3-agent pipeline performs triage, investigation, and root cause analysis.
6. A PDF incident report is generated with full evidence and findings.
7. The notifier emails the report to the on-call recipient.
8. The remediation flow opens a draft GitHub pull request for human review.

The 3-agent pipeline runs inside the Docker stack as part of `incident-agent-workflow`:

| Agent | Role | Responsibility |
|---|---|---|
| Agent 1 — Triage | Service resolution | Identifies the affected service, classifies severity, resolves config from registry |
| Agent 2 — Investigation | Runtime evidence | Runs health checks, scans logs, extracts stack traces and request context |
| Agent 3 — Code Analysis | Root cause | Reads source context around failure points and suggests fixes |

---

## System Design

```
A service fails
       ↓
Prometheus detects the outage
       ↓
Alertmanager calls the AI agent
       ↓
Agent gathers context (Prometheus metrics + Loki logs)
       ↓
3-Agent Pipeline runs inside incident-agent-workflow
  ┌──────────────────────────────────────────────┐
  │  Agent 1: Triage                             │
  │  Classifies severity, resolves service config│
  │               ↓                              │
  │  Agent 2: Investigation                      │
  │  Health checks, log scan, stack trace extract│
  │               ↓                              │
  │  Agent 3: Code Analysis                      │
  │  Source-level root cause, fix suggestion     │
  └──────────────────────────────────────────────┘
       ↓
PDF incident report generated (WeasyPrint)
       ↓
Notifier emails the report
       ↓
Draft GitHub PR opened for human review
       ↓
Engineers review evidence and merge when ready
```

### A service fails

A monitored service crashes, becomes unreachable, or starts returning errors. Each service exposes `/metrics` and writes logs under `apps/<service>/logs/`.

### Prometheus detects the outage

Prometheus scrapes targets from `monitoring/targets.docker.yml`. When `up == 0` for 30 seconds, or another rule in `monitoring/alert-rules.yml` fires, the incident starts.

### Alertmanager calls the AI agent

When a rule fires, Alertmanager sends an Alertmanager-compatible payload to:

```
http://incident-agent-workflow:9100/alerts
```

### The agent gathers context

The workflow queries Prometheus for service health and 5xx rates, then queries Loki for recent logs using the same service label from the alert.

### The 3-agent pipeline runs

The pipeline is orchestrated by `pipeline.py` inside the `incident-agent-workflow` container. Each agent hands its output to the next:

- **TriageAgent** — resolves the service in `service_registry.json`, classifies error type and severity
- **InvestigationAgent** — hits health endpoints, reads log files, extracts stack traces
- **CodeAnalysisAgent** — reads source files referenced in the stack trace, produces root-cause analysis

### PDF report is generated

WeasyPrint renders a structured PDF with the full investigation evidence, agent findings, timeline, and remediation notes.

### Notifier sends the incident email

The notifier receives the pipeline result and emails the PDF report with the alert name, service, summary, and analysis.

### Humans stay in control

When the investigation finds a concrete remediation, the system opens a draft GitHub pull request. Engineers review the evidence, tests, and diff before merging and resolving the incident.

---

## Agentic Investigation and Git Flow

```
Incident Alert
      ↓
Agent 1 — Triage
  Resolves service from service_registry.json
  Maps alert → health URLs, log paths, repo paths, language
      ↓
Agent 2 — Investigation
  Checks service health endpoints
  Reads logs, searches for errors
  Extracts stack traces and request context
      ↓
Agent 3 — Code Analysis
  Reads source files and line ranges from stack trace
  Moves from "what failed" to "why this code failed"
      ↓
PDF Report + Draft GitHub PR
  Evidence packaged into report
  Proposed fix opens as draft PR for human review
```

---

## How We Built It

The full environment is orchestrated with Docker Compose.

### Application Layer

- `weather-app1` — FastAPI weather service on port 8000
- `mongo-api-service` — FastAPI CRUD service backed by MongoDB on port 9000
- Prometheus `/metrics` endpoints via `prometheus-fastapi-instrumentator`
- File-based logs mounted into Promtail

### Observability Stack

- **Prometheus** — metrics scraping and alert rules
- **Alertmanager** — alert grouping and webhook dispatch
- **Promtail + Loki** — log aggregation
- **Grafana** — metrics and log exploration

### Alert Workflow

1. `incident-agent-workflow` receives `POST /alerts`
2. Queries Prometheus for `up` and 5xx-rate signals
3. Queries Loki for recent service logs
4. Builds a structured incident context object
5. Runs the 3-agent pipeline (`pipeline.py`)
6. Generates a PDF report (WeasyPrint, `reports/generator.py`)
7. Posts the result to the notifier for email delivery
8. Opens a draft GitHub PR when a fix is identified

### Notification System

A FastAPI notifier service runs under `apps/notifier/`.

- SMTP email with PDF attachment support
- The workflow posts incident results to `/notify`
- Email includes service name, alert, summary, analysis, and the PDF report
- Local demo mail tools like Mailpit work by pointing the notifier SMTP settings to the local server

### Reporting

PDF reports are generated by WeasyPrint inside the Docker container and written under `apps/incident-agent-workflow/reports/`. The repo also includes host-side utilities:

- `apps/log_watcher.py` — scans log files and calls the analysis pipeline
- `apps/monitor_service.py` — monitors service health
- `apps/report_generator.py` — generates Word (.docx) postmortem documents

---

## Repository Layout

```
.
├── docker-compose.yml
├── architecture.html
├── README.md
├── apps/
│   ├── weather-app1/
│   ├── mongo-api-service/
│   ├── incident-agent-workflow/
│   │   ├── agents/
│   │   │   ├── triage.py
│   │   │   ├── investigation.py
│   │   │   ├── code_analysis.py
│   │   │   └── quick_analysis.py
│   │   ├── tools/
│   │   │   ├── logs.py
│   │   │   ├── health.py
│   │   │   └── git.py
│   │   ├── reports/
│   │   │   └── generator.py
│   │   ├── pipeline.py
│   │   ├── main.py
│   │   ├── config.py
│   │   └── service_registry.json
│   ├── notifier/
│   ├── log_watcher.py
│   ├── monitor_service.py
│   └── report_generator.py
└── monitoring/
    ├── prometheus.yml
    ├── targets.docker.yml
    ├── alert-rules.yml
    ├── alertmanager.yml
    ├── loki-config.yml
    ├── promtail-config.yml
    └── grafana/provisioning/
```

---

## Run Locally

### Prerequisites

- Docker and Docker Compose
- [Ollama](https://ollama.com/download) running on your host machine (or an OpenAI API key)

**With Ollama (default):**
```bash
ollama pull mistral-nemo
ollama serve
```

If Ollama is already running, `ollama serve` may report that the port is in use. That is fine.

**With OpenAI** — set these in `apps/incident-agent-workflow/.env`:
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
```

### Configure Services

Copy the example env files and fill in your values:

```bash
cp apps/incident-agent-workflow/.env.example apps/incident-agent-workflow/.env
cp apps/notifier/.env.example apps/notifier/.env
cp apps/mongo-api-service/.env.example apps/mongo-api-service/.env
```

### Start the Stack

```bash
docker compose up -d --build
```

Check status:
```bash
docker compose ps
```

Stop the stack:
```bash
docker compose down
```

### Service URLs

| Service | URL |
|---|---|
| Weather API | http://localhost:8000 |
| Mongo API | http://localhost:9000 |
| Incident workflow | http://localhost:9100 |
| Notifier | http://localhost:8002 |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| Grafana | http://localhost:3000 |
| Loki | http://localhost:3100 |
| MongoDB | localhost:27017 |

Grafana credentials: `admin` / `admin`

---

## Verify the Demo

Check service health:
```bash
curl http://localhost:8000/
curl http://localhost:9000/health
curl http://localhost:9100/health
```

Check Prometheus targets:
```
http://localhost:9090/targets
```

Create a Mongo item:
```bash
curl -X POST http://localhost:9000/items/ \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","description":"test item","value":42}'
```

Trigger a test alert manually:
```bash
# Git Bash / Linux / Mac
curl -X POST http://localhost:9100/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "ServiceDown",
          "service": "weather-app1"
        },
        "annotations": {
          "summary": "weather-app1 is not responding"
        }
      }
    ]
  }'

# PowerShell
Invoke-WebRequest -Method POST http://localhost:9100/alerts `
  -ContentType "application/json" `
  -Body '{"alerts":[{"status":"firing","labels":{"alertname":"ServiceDown","service":"weather-app1"},"annotations":{"summary":"weather-app1 is not responding"}}]}'
```

Watch the pipeline run:
```bash
docker compose logs -f incident-agent-workflow
```

Look for log lines like `[Pipeline ABC123] TriageAgent running…`, `InvestigationAgent done`, `CodeAnalysisAgent done`. When complete, a PDF is generated and the notifier is called.

---

## Active Alerts

| Alert | Condition | Severity |
|---|---|---|
| `ServiceDown` | Prometheus cannot scrape a service for 30 seconds | critical |
| `MongoDependencyDown` | mongo-api-service cannot ping MongoDB for 30 seconds | critical |
| `Service5xxErrors` | A service has non-zero 5xx rate for 30 seconds | warning |

---

## Useful Queries

**Prometheus:**
```promql
up
sum by (service) (up)
sum by (service, handler, method, status) (rate(http_requests_total[1m]))
sum by (service) (rate(http_requests_total{status="5xx"}[2m]))
dependency_up{service="mongo-api-service", dependency="mongodb"}
```

**Loki:**
```logql
{service="weather-app1"}
{service="mongo-api-service"}
{service="incident-agent-workflow"}
{service="incident-agent-workflow"} |= "Pipeline"
{service="incident-agent-workflow"} |= "CodeAnalysisAgent"
{service="mongo-api-service"} |= "ERROR"
```

---

## API Reference

### weather-app1

| Method | Path | Description |
|---|---|---|
| GET | `/` | Basic service check |
| GET | `/weather/latitude={lat}&longitude={lon}` | Fetch weather data from Open-Meteo |
| GET | `/metrics` | Prometheus metrics |

### mongo-api-service

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/health/ready` | MongoDB readiness check |
| POST | `/items/` | Create item |
| GET | `/items/` | List items |
| GET | `/items/{item_id}` | Get item |
| PUT | `/items/{item_id}` | Update item |
| DELETE | `/items/{item_id}` | Delete item |
| GET | `/metrics` | Prometheus metrics |

### incident-agent-workflow

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/alerts` | Alertmanager webhook receiver |
| GET | `/metrics` | Prometheus metrics |

---

## Challenges We Ran Into

### Docker to Host LLM Communication

Ollama runs on the host machine while the workflow runs in Docker. The workflow uses `host.docker.internal:11434` so containers can reach the host LLM server.

### Integrating the 3-Agent Pipeline Inside Docker

Keeping all three agents inside the same Docker service required careful orchestration — each agent hands structured output to the next, and failures in one agent must not silently break the chain. Logging every stage with a pipeline ID made debugging tractable.

### Observability Integration

The system depends on consistent labels across Prometheus, Alertmanager, Loki, and Promtail. If a service label or log path is wrong, the agent can receive the alert but miss the log context.

### Reliable LLM JSON Output

Getting the LLM to return structured JSON consistently across all three agent stages required prompt engineering and output validation. The pipeline had to handle cases where the model returned prose instead of JSON.

### PDF Generation Inside Docker

WeasyPrint has complex font and rendering dependencies that behave differently inside a minimal Docker container versus a host machine. Getting clean PDF output required tuning the Dockerfile and font configuration.

### Safe Draft PR Automation

Automatically proposing fixes creates risk if the system writes too much or merges without review. The project uses draft GitHub pull requests as the handoff point so humans approve the remediation.

---

## Accomplishments

- Built a complete local incident-response loop from alert to AI-generated PDF report.
- Connected metrics, logs, alerts, and LLM context instead of building a standalone chatbot.
- Implemented a 3-agent pipeline that runs entirely inside Docker — no separate host process needed.
- Added a production-style observability stack: Prometheus, Alertmanager, Loki, Promtail, and Grafana.
- Generated structured PDF incident reports with WeasyPrint.
- Added notifier-based incident emails with PDF attachments.
- Added GitHub draft PR handoff for proposed remediations.

---

## What We Learned

- Alerts are only the trigger; context is the real product.
- AI analysis is only useful when it is grounded in telemetry.
- Labels and log paths matter as much as the model.
- Structured summaries are more useful than long explanations during incidents.
- Automation should produce reviewable suggestions before it makes changes.
- Getting reliable structured output from an LLM requires as much engineering as the surrounding plumbing.

---

## What's Next

- Confidence scoring on proposed fixes
- Slack and PagerDuty notification channels
- Runbook lookup and Jira/Linear issue creation
- Smarter routing: simple alerts use fast triage, complex alerts use the full pipeline

---

## Troubleshooting

### incident-agent-workflow logs an LLM error

Check that Ollama is running and the model is available:
```bash
ollama list
ollama pull mistral-nemo
```

### Prometheus target is DOWN

```bash
docker compose ps
docker compose logs weather-app1
docker compose logs incident-agent-workflow
```

### Mongo API fails to start

Confirm `apps/mongo-api-service/.env` exists and MongoDB is healthy:
```bash
docker compose ps mongo
docker compose logs mongo
```

### Grafana has no logs

```bash
docker compose logs promtail
docker compose logs loki
```

Confirm log files exist under `apps/*/logs/`.

### PDF not generated

```bash
docker compose logs incident-agent-workflow | grep -i "pdf\|weasy\|report"
```
