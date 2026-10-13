# Monitoring

Argus is a monitoring product, and it is monitored itself with Prometheus and Grafana from
[kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack).

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --version 92.3.1 -n monitoring --create-namespace \
  -f monitoring/kube-prometheus-values.yaml --wait
```

Install this **before** Argus. The Argus chart renders its ServiceMonitor, PrometheusRule
and dashboard only when the Prometheus Operator CRDs exist.

## What gets scraped

The backend's `/metrics` endpoint serves two kinds of series:

| Series | Source | Meaning |
|---|---|---|
| `http_requests_total`, `http_request_duration_seconds` | prometheus-fastapi-instrumentator | Request rate, errors and latency per route |
| `argus_heartbeats_total{service,status}` | counter in the ingest route | Heartbeats accepted, by result |
| `argus_service_up{service}` | computed at scrape time | 1 if up or degraded, 0 if down |
| `argus_uptime_ratio{service,window}` | computed at scrape time | Good slots / judged slots for 5m, 1h, 24h |
| `argus_burn_rate{service,window}` | computed at scrape time | Error-budget burn rate; 1 = on budget |
| `argus_error_budget_remaining_ratio{service}` | computed at scrape time | 24h budget left; negative once breached |
| `argus_slo_target_ratio{service}` | computed at scrape time | The configured target |

The SLO gauges are computed from the database on every scrape by a custom collector. No
background job keeps state, so every backend replica reports the same values. Queries
therefore use `max by (service)` to collapse the duplicate series from each replica.

## Alerts

`helm/argus/templates/prometheusrule.yaml` uses the multi-window, multi-burn-rate pattern
from chapter 5 of the Google SRE workbook:

| Alert | Fires when | Severity |
|---|---|---|
| `ArgusErrorBudgetFastBurn` | 1h **and** 5m burn rate > 14.4× for 2m | page |
| `ArgusErrorBudgetSlowBurn` | 24h **and** 1h burn rate > 1× for 15m | ticket |
| `ArgusServiceDown` | a service is down for 1m | page |
| `ArgusErrorBudgetExhausted` | the 24h budget is below zero for 5m | ticket |

A 14.4× burn rate would exhaust a 30-day budget in about two days. The short window
makes the alert clear soon after recovery. Alertmanager is disabled on minikube, so alerts
are viewed on Prometheus's **Alerts** page.

## Dashboard

`helm/argus/dashboards/argus.json` ships as a ConfigMap labelled `grafana_dashboard: "1"`.
The Grafana sidecar searches every namespace (`searchNamespace: ALL`), so the dashboard
**Argus — SLOs and error budgets** appears without a manual import.

```bash
kubectl -n monitoring port-forward svc/monitoring-grafana 3001:80
kubectl -n monitoring get secret monitoring-grafana -o jsonpath='{.data.admin-password}' | base64 -d; echo
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
```
