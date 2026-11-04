# Fitness Evaluation & Voice Scoring

## The Evaluation Formula

Fitness is computed in `backend/app/darwin/fitness.py`. 

### 1. Base Multi-Dimensional Score
$$\text{Base Score} = 0.30T + 0.25Q + 0.20R + 0.15L + 0.10E$$

Where:
- $T$ = Task Completion Score (0-100)
- $Q$ = Response Quality Score (0-100)
- $R$ = Context Retention Score (0-100)
- $L$ = Response Latency Score (0-100)
- $E$ = Error Recovery Score (0-100)

### 2. Wispr Flow Dictation Dimensions
For dictation pipelines, evaluation incorporates 5 specialized dimensions:
- **Intent Fidelity:** Does the agent output the final intended message after self-correction?
- **Cleanup Quality:** Are stutters and filler words removed without dropping valid vocabulary?
- **Formatting Correctness:** Are capitalization and punctuation appropriate?
- **Entity Accuracy:** Are numbers, currency amounts, dates, and names preserved?
- **Command Handling:** Are inline formatting instructions executed rather than typed literally?

### 3. Final Adversarial Fitness
$$\text{Overall Score} = 0.60 \times \text{Base Score} + 0.40 \times \text{Dictation Score} - \text{Deterministic Penalty}$$

$$\text{Fitness} = 1.0 - \frac{\text{Overall Score}}{100.0}$$

- Agent Score = 100% $\to$ Fitness = 0.0 (Attack Failed)
- Agent Score = 20% $\to$ Fitness = 0.8 (Strong Attack Found)
- Agent Score = 0% $\to$ Fitness = 1.0 (Critical Crash / Failure)

