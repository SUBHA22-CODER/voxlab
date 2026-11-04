# Genome Representation & Mutation Operators

## Genome Dataclass

In `backend/app/darwin/genome.py`, test scenarios are encoded as structured genomes:

```python
@dataclass
class TurnGene:
    user_utterance: str
    hesitation_ms: int = 0
    noise_level: float = 0.0
    expected_response_hints: list[str] = field(default_factory=list)
    barge_in: bool = False

@dataclass
class Genome:
    id: str
    persona: str
    strategy: str
    turns: list[TurnGene]
    generation: int = 0
    fitness: float = 0.0
```

---

## Mutation Operators

1. **Add Turn (`MUTATE_ADD_TURN`):** Appends an utterance adhering to the persona's adversarial strategy.
2. **Remove Turn (`MUTATE_REMOVE_TURN`):** Prunes a turn to test whether earlier prompts triggered latent state issues.
3. **Swap Turns (`MUTATE_SWAP_TURNS`):** Transposes two consecutive turns to test conversation history dependency.
4. **Hesitation Mutation (`MUTATE_HESITATION`):** Jitters inter-word hesitation pause length (0 to 3000 ms).
5. **Utterance Perturbation:** Injects fillers (*"um, actually"*) or homophones (*"four" -> "for"*).

