from __future__ import annotations

import time

from flask import Flask, Response, g, request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client import ProcessCollector, PlatformCollector, GCCollector


SERVICE_NAME = "user_api"


def init_metrics(app: Flask) -> None:
    registry = CollectorRegistry()
    GCCollector(registry=registry)
    PlatformCollector(registry=registry)
    ProcessCollector(namespace=f"ticketrush_{SERVICE_NAME}", registry=registry)

    requests_total = Counter(
        "ticketrush_user_api_http_requests_total",
        "Total number of HTTP requests.",
        ("method", "route", "status"),
        registry=registry,
    )
    request_duration = Histogram(
        "ticketrush_user_api_http_request_duration_seconds",
        "HTTP request latency in seconds.",
        ("method", "route", "status"),
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        registry=registry,
    )
    request_size = Histogram(
        "ticketrush_user_api_http_request_size_bytes",
        "HTTP request size in bytes.",
        ("method", "route"),
        buckets=(100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600, 51200, 102400, 204800),
        registry=registry,
    )
    response_size = Histogram(
        "ticketrush_user_api_http_response_size_bytes",
        "HTTP response size in bytes.",
        ("method", "route"),
        buckets=(100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600, 51200, 102400, 204800),
        registry=registry,
    )
    in_flight = Gauge(
        "ticketrush_user_api_http_requests_in_flight",
        "Current number of HTTP requests being served.",
        registry=registry,
    )

    @app.before_request
    def metrics_before_request():
        if request.path == "/metrics":
            return None
        g.metrics_start_time = time.perf_counter()
        in_flight.inc()
        return None

    @app.after_request
    def metrics_after_request(response):
        if request.path == "/metrics":
            return response

        route = "unmatched"
        if request.url_rule is not None:
            route = request.url_rule.rule

        method = request.method
        status = str(response.status_code)
        elapsed = time.perf_counter() - getattr(g, "metrics_start_time", time.perf_counter())

        requests_total.labels(method, route, status).inc()
        request_duration.labels(method, route, status).observe(elapsed)
        request_size.labels(method, route).observe(float(request.content_length or 0))
        response_size.labels(method, route).observe(float(response.calculate_content_length() or 0))
        in_flight.dec()
        g.metrics_observed = True
        return response

    @app.teardown_request
    def metrics_teardown_request(_error):
        if (
            request.path != "/metrics"
            and hasattr(g, "metrics_start_time")
            and not getattr(g, "metrics_observed", False)
        ):
            in_flight.dec()

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)
