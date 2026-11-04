# Data Model & Schema Specification

> **Assumptions:**
> - Database: SQLite in WAL mode (`backend/voxlab.db`) for development; PostgreSQL 16 for production.
> - Managed via SQLAlchemy 2.0 async declarations.

---

## 1. Entity Relationship Overview

```
+---------------+        1:N        +---------------+
|     User      | +---------------> |     Agent     |
+---------------+                   +---------------+
        |                                   |
        | 1:N                               | 1:N
        v                                   v
+---------------+        1:N        +---------------+
|   DarwinRun   | +---------------> |  DarwinFinding|
+---------------+                   +---------------+
        |
        | 1:N
        v
+------------------+
| DarwinGeneration |
+------------------+
```

---

## 2. Table Schemas

### 2.1 `users`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, Auto-increment | User identifier |
| `email` | String(255) | Unique, Indexed, Not Null | User email address |
| `password_hash` | String(255) | Not Null | Bcrypt password hash |
| `created_at` | DateTime | Default UTC now | Registration timestamp |

### 2.2 `agents`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, Auto-increment | Agent identifier |
| `user_id` | Integer | FK(`users.id`), Indexed | Owning user |
| `name` | String(255) | Not Null | Display name |
| `description` | Text | Default `""` | Agent description |
| `endpoint` | String(1024) | Not Null | HTTP / WebSocket URL |
| `agent_type` | String(32) | Default `"http"` | Connection protocol |
| `auth_config_encrypted` | Text | Nullable | Fernet-encrypted auth headers |
| `config` | JSON | Default `{}` | Options (timeout_s, latency_budget) |
| `created_at` | DateTime | Default UTC now | Creation timestamp |

### 2.3 `darwin_runs`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, Auto-increment | Campaign identifier |
| `user_id` | Integer | FK(`users.id`), Indexed | Owning user |
| `agent_id` | Integer | FK(`agents.id`), Indexed | Target agent |
| `status` | String(32) | Default `"queued"` | `queued`, `running`, `completed`, `failed` |
| `progress` | Integer | Default 0 | Progress percentage (0–100) |
| `config` | JSON | Not Null | Population size, generations, seed, personas |
| `stats` | JSON | Default `{}` | Sessions used, best fitness, findings count |
| `error` | Text | Nullable | Error details if failed |
| `started_at` | DateTime | Default UTC now | Start timestamp |
| `finished_at` | DateTime | Nullable | Completion timestamp |

### 2.4 `darwin_generations`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, Auto-increment | Generation record identifier |
| `run_id` | Integer | FK(`darwin_runs.id`), Indexed | Parent campaign run |
| `generation_index` | Integer | Not Null | Generation counter (0, 1, 2...) |
| `best_fitness` | Float | Not Null | Highest attack fitness in gen |
| `avg_fitness` | Float | Not Null | Average population fitness |
| `stats` | JSON | Default `{}` | Population size, best overall score |
| `created_at` | DateTime | Default UTC now | Generation finish timestamp |

### 2.5 `darwin_findings`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, Auto-increment | Vulnerability finding identifier |
| `run_id` | Integer | FK(`darwin_runs.id`), Indexed | Parent campaign run |
| `persona` | String(64) | Not Null | Attacking persona |
| `strategy` | String(128) | Not Null | Attack vector description |
| `genome` | JSON | Not Null | Full attack candidate genome |
| `minimized_steps` | JSON | Not Null | Repro steps post-ddmin |
| `original_steps_count` | Integer | Not Null | Pre-minimization turn count |
| `minimized_steps_count` | Integer | Not Null | Minimal turn count |
| `fitness` | Float | Not Null | Attack fitness score |
| `diagnosis` | JSON | Not Null | AI root cause and fix recommendation |
| `trace_id` | String(64) | Not Null | Trace identifier |
| `session_id` | Integer | Nullable | Execution session ID |
