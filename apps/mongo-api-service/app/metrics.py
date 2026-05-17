from prometheus_client import Gauge


dependency_up = Gauge(
    "dependency_up",
    "Whether an external dependency is reachable. 1 is up, 0 is down.",
    ["service", "dependency"],
)

dependency_last_check_timestamp_seconds = Gauge(
    "dependency_last_check_timestamp_seconds",
    "Unix timestamp of the last dependency health check.",
    ["service", "dependency"],
)
