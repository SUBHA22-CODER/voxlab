# End-to-End Testing Guide

## Running the E2E Verification Suite

To verify the complete VoxLab platform locally before submitting changes:

### 1. Launch Demo Voice Agents
In two separate terminals:
```bash
# Agent 1: Customer Support Agent
cd agent-examples/customer-support-agent
python -m uvicorn main:app --port 8100

# Agent 2: Wispr Flow Dictation Agent
cd agent-examples/dictation-agent
python -m uvicorn main:app --port 8200
```

### 2. Run Backend Pytest Suite
In a third terminal:
```bash
cd backend
python -m pytest -v
```

### 3. Verify Next.js Web Application
In a fourth terminal:
```bash
cd frontend
npm run build
```
Ensure build compiles with zero TypeScript or Webpack errors.
