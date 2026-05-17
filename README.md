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
monitoring/
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
grafana            http://127.0.0.1:3000
loki               http://127.0.0.1:3100
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
