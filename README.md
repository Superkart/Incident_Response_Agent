# Incident Response Agent Local Services

This repo is organized for multiple local services plus one shared monitoring stack.

```text
docker-compose.yml
apps/
  weather-app1/
    Dockerfile
    main.py
  mongo-api-service/
    Dockerfile
    app/
  incident-agent-workflow/
    Dockerfile
    main.py
monitoring/
  alert-rules.yml
  alertmanager.yml
  grafana/provisioning/datasources/datasources.yml
  loki-config.yml
  prometheus.yml
  promtail-config.yml
  targets.yml
  targets.docker.yml
  README.md
requirements.txt
```

Put each new service under `apps/`:

```text
apps/service-app2/
apps/service-app3/
apps/service-app4/
```

Each service should expose `/metrics` if you want Prometheus and Grafana to monitor it.

Run everything together:

```bash
docker compose up --build
```

This starts:

```text
weather-app1       http://127.0.0.1:8000
mongo-api-service  http://127.0.0.1:9000
prometheus         http://127.0.0.1:9090
alertmanager       http://127.0.0.1:9093
grafana            http://127.0.0.1:3000
loki               http://127.0.0.1:3100
agent workflow     http://127.0.0.1:9100
mongodb            localhost:27017
```

Prometheus uses `monitoring/targets.docker.yml` in the full Docker stack.
Use `monitoring/targets.yml` only when you run services directly on your host.

Grafana is provisioned with two data sources:

```text
Prometheus  http://prometheus:9090
Loki        http://loki:3100
```

To view logs in Grafana:

```text
Explore -> select Loki -> run a LogQL query
```

Useful LogQL:

```logql
{service="weather-app1"}
{service="mongo-api-service"}
{service="weather-app1"} |= "ERROR"
{service="mongo-api-service"} |= "ERROR"
```

Grafana login:

```text
admin / admin
```

Alerting flow:

```text
Prometheus alert rule
  -> Alertmanager
  -> incident-agent-workflow /alerts webhook
  -> queries Prometheus and Loki for context
  -> writes workflow logs to apps/incident-agent-workflow/logs/workflow.log
```

Current alerts:

```text
ServiceDown
MongoDependencyDown
Service5xxErrors
```

The Mongo API exports this dependency metric:

```promql
dependency_up{service="mongo-api-service", dependency="mongodb"}
```

Your real agentic workflow can replace [apps/incident-agent-workflow/main.py](apps/incident-agent-workflow/main.py).
