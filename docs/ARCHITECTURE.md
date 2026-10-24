# ServiceGuard Architecture

## Components

```mermaid
flowchart LR
  subgraph WIN["Windows 11 laptop"]
    subgraph WSL["WSL 2: Ubuntu 24.04 with systemd"]
      SG["serviceguard.py<br/>monitor loop, incidents"]
      CH["checker.py<br/>HTTP status + content"]
      RC["recovery.py<br/>nginx -t, restart, is-active"]
      NG["Nginx test site<br/>port 8080"]
      LG["logs/serviceguard.log<br/>logs/incidents.jsonl"]
    end
  end
  SG --> CH
  CH -- "GET /health and GET /" --> NG
  SG -- "after threshold failures" --> RC
  RC -- "sudo: nginx -t, systemctl restart" --> NG
  SG --> LG
```

## Incident lifecycle

```mermaid
flowchart TD
  A["Check /health and /"] --> B{"Both OK?"}
  B -- yes --> A
  B -- no --> C["Count consecutive failure"]
  C --> D{"Failures >= threshold?"}
  D -- no --> A
  D -- yes --> E["Open incident, write JSON event"]
  E --> F{"--recover on and attempts left?"}
  F -- no --> J["Log: manual intervention required"]
  F -- yes --> G["nginx -t"]
  G -- fails --> H["Skip restart, count attempt"]
  G -- passes --> I["systemctl restart, then is-active"]
  H --> K["Re-check over HTTP"]
  I --> K
  K --> B
  J --> A
  B -. "OK after an incident" .-> L["Log INCIDENT RESOLVED with downtime"]
```

## Notes

- Everything runs on one local machine. There is no cloud component.
- Recovery is verified by a fresh HTTP check, not by the restart result.
- The sudoers rule allows only `nginx -t` and `systemctl restart nginx`.
