# ServiceGuard Architecture

## Components

```mermaid
flowchart LR
  subgraph WSL["WSL 2: Ubuntu 24.04 with systemd"]
    NG["Nginx load balancer :8080"]
    BA["backend-a :9001"]
    BB["backend-b :9002"]
    SG["ServiceGuard (systemd service)"]
    MX["metrics endpoint :9101"]
    NE["Node Exporter :9100"]
    PR["Prometheus :9090"]
    GF["Grafana :3000"]
    LG["logs: incidents.jsonl, serviceguard.log"]
  end
  NG --> BA
  NG --> BB
  SG -- "GET /" --> NG
  SG -- "GET /health" --> BA
  SG -- "GET /health" --> BB
  SG -- "sudo restart, allow-listed" --> NG
  SG --> MX
  SG --> LG
  PR -- scrape --> MX
  PR -- scrape --> NE
  GF -- query --> PR
```

## Per-target incident lifecycle

Each target (frontend, backend-a, backend-b) has its own failure counter and
incident state.

```mermaid
flowchart TD
  A["Check target"] --> B{"Check passed?"}
  B -- yes --> R{"Incident open?"}
  R -- yes --> S["Log INCIDENT RESOLVED with downtime"]
  R -- no --> A
  S --> A
  B -- no --> C["Count consecutive failure"]
  C --> D{"Failures >= threshold?"}
  D -- no --> A
  D -- yes --> E["Open incident, write JSON event"]
  E --> F{"--recover on and attempts left?"}
  F -- no --> J["Log: manual intervention required"]
  F -- yes --> G{"Service is nginx?"}
  G -- yes --> H["nginx -t"]
  H -- fails --> K["Skip restart, count attempt"]
  H -- passes --> I["systemctl restart, then is-active"]
  G -- no --> I
  I --> A
  K --> A
  J --> A
```

## Notes

- Everything runs on one local machine. There is no cloud component.
- Recovery is confirmed by the next HTTP check, not by the restart command.
- The sudoers rule allows only `nginx -t` and restarts of nginx, sg-backend-a
  and sg-backend-b. The code also keeps its own allow-list.
- systemd watches ServiceGuard (`Restart=on-failure`). ServiceGuard watches
  the web services.
