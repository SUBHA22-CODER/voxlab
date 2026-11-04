# API Specification

> **Base URL:** `http://localhost:8001/api` (Production: configurable via `NEXT_PUBLIC_API_URL`)
> **Authentication:** Bearer JWT in `Authorization: Bearer <TOKEN>` header.

---

## 1. Authentication Endpoints

### 1.1 Register User
- **POST** `/auth/register`
- **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword123"
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "access_token": "<JWT_TOKEN>",
    "token_type": "bearer"
  }
  ```
- *Note:* Automatically provisions starter agents (`Customer Support Agent` and `Wispr Flow Dictation Agent`).

### 1.2 Login User
- **POST** `/auth/login`
- **Response (200 OK):** Token response object.

---

## 2. Darwin Fuzzing Endpoints

### 2.1 List Attack Personas
- **GET** `/darwin/personas`
- **Response (200 OK):**
  ```json
  [
    {
      "id": "self_corrector",
      "name": "Self Corrector",
      "description": "Simulates rapid mid-sentence intent corrections.",
      "is_dictation_focused": true,
      "strategies": ["Rapid date correction", "Item modification"]
    }
  ]
  ```

### 2.2 Launch Fuzzing Campaign
- **POST** `/darwin/runs`
- **Request Body:**
  ```json
  {
    "agent_id": 2,
    "population_size": 6,
    "generations": 5,
    "top_k": 2,
    "personas": ["self_corrector", "filler_heavy_rambler"],
    "seed": 42,
    "failure_threshold": 0.5
  }
  ```
- **Response (202 Accepted):** Returns initialized `DarwinRunOut` object.

### 2.3 Get Campaign Status & Detail
- **GET** `/darwin/runs/{id}`
- **Response (200 OK):** Returns run metadata, `generations_data`, and list of `findings`.

### 2.4 Stop Running Campaign
- **POST** `/darwin/runs/{id}/cancel`
- **Response (200 OK):** `{ "status": "cancelled" }`

### 2.5 Export Finding to Regression Suite
- **POST** `/darwin/findings/{id}/export`
- **Response (200 OK):** Returns exported scenario path in `scenarios/regression/`.

### 2.6 Verify Auto-Doctor Patch
- **POST** `/darwin/findings/{id}/verify-patch`
- **Response (200 OK):**
  ```json
  {
    "verified": true,
    "patch_diff": "--- cleaner.py\n+++ cleaner.py\n...",
    "pre_patch_fitness": 0.57,
    "post_patch_fitness": 0.05,
    "baseline_passed": true
  }
  ```
