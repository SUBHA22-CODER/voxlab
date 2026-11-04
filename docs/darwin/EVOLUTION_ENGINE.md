# Darwin Evolution Engine

## Genetic Evolution Loop

The evolution loop in `backend/app/darwin/evolution.py` controls population dynamics across multiple generations:

1. **Initialization:**
   - Samples initial genomes across active personas.
   - Populates initial step sequences with randomized speech parameters (hesitation pauses, audio noise levels, persona-specific utterance seeds).

2. **Fitness Evaluation:**
   - Executes each candidate scenario through the VoxLab `ScenarioRunner`.
   - Records full event traces and latency metrics.
   - Computes fitness:
     $$\text{Fitness} = 1.0 - \frac{\text{Overall Score}}{100.0}$$
   - Higher fitness represents a stronger adversarial attack that causes greater agent degradation.

3. **Selection & Elite Preservation:**
   - Ranks candidates by fitness descending.
   - Preserves top-K elite candidates without mutation into the next generation.

4. **Mutation & Crossover:**
   - Applies stochastic mutation operators to non-elite parents:
     - Adding or removing conversational turns.
     - Swapping turn order.
     - Mutating hesitation parameters and speech fillers.
     - Injecting homophones or self-correction patterns.

5. **Budget Cap Enforcement:**
   - Total executions are capped at `min(pop_size * generations, 60)`.
   - Prevents memory leaks, excessive network traffic, and API exhaustion.
