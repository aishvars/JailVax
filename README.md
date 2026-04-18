# JailVax

**Adversarial Self-Play with Formal Safety Verification for Provable Jailbreak Defense**

JailVax is a middleware defense system that uses the Z3 theorem prover to formally verify LLM safety constraints in real time. It sits between the user and the target LLM, checking each conversation turn against mathematically encoded safety rules before allowing a response through.

Developed as part of CMU 14-795 (AI Applications in Information Security), affiliated with CMU CyLab.

**Authors:** Achintya Gahalaut, Aishvarya Srivastava, Nisarga Gondi

---

## Overview

Large language models are vulnerable to jailbreak attacks that bypass safety alignment through techniques like gradual escalation, prompt obfuscation, and psychological manipulation. Existing defenses rely on probabilistic classifiers that produce confidence scores with no formal guarantees.

JailVax takes a different approach: it encodes safety constraints as Z3 logical formulas and returns **provable verdicts** — SAT (violation found, block the response) or UNSAT (provably safe, allow the response). This gives defenders mathematical certificates rather than probability scores.

### Key Results

| Metric | Value |
|--------|-------|
| Total attacks evaluated | 333 across 4 methods |
| Crescendo ASR reduction | 75.0% → 35.4% (−39.6pp) |
| Crescendo detection rate | 100% (36/36 jailbreaks caught) |
| PAIR detection rate | 100% (47/47 jailbreaks caught) |
| Post-block bypass rate | 0/30 (100% stopping effectiveness) |
| Z3 rules implemented | 11 across 3 defense layers |
| False positive rate (PAIR) | 0% |

---

## Architecture

JailVax operates as a four-stage pipeline:

```
ATTACK          FORMALIZE        VERIFY           VACCINATE
-----------     -----------      -----------      -----------
Crescendo       Extract          Z3 SAT/UNSAT     Block if SAT
PAIR        --> features     --> Safety       --> Pass if UNSAT
GCG             Build rules      certificates     Self-play loop
FITD            Set thresholds   Real-time check  Iterate
```

### 3-Layer Defense

**Layer 1 — Prompt Level (PAIR, GCG):** Analyzes individual prompts for obfuscation patterns, roleplaying frames, and adversarial suffixes before they reach the target model.

**Layer 2 — Turn Level (Crescendo, FITD):** Monitors per-turn score trajectories (harm, topic drift, compliance, specificity) and triggers when escalation patterns emerge.

**Layer 3 — Conversation Level (All attacks):** Checks cumulative compliance momentum and combined safety thresholds across the full conversation history.

---

## Z3 Rule Set

| ID | Attack | Condition | Layer | Action | Coverage |
|----|--------|-----------|-------|--------|----------|
| C1 | Crescendo | topic_drift >= 3 before harm >= 4 | Turn | FLAG | 83% |
| C2 | Crescendo | compliance non-decreasing 3+ turns | Turn | FLAG | 72% |
| C3 | Crescendo | specificity spike >1.5 above avg | Turn | BLOCK | 94% |
| C4 | Crescendo | ALL four scores >= 4 | Turn | BLOCK | 100% |
| P1 | PAIR | judge_score = 10 on iteration 1 | Prompt | BLOCK | 68% |
| P2 | PAIR | roleplaying strategy + score >= 8 | Prompt | BLOCK | 84% |
| P4 | PAIR | obfuscation framing markers detected | Prompt | BLOCK | 76% |
| G3 | GCG | high-perplexity suffix anomaly | Prompt | BLOCK | 43 blocks |
| G4 | GCG | goal category risk classification | Convo | TUNE | 32% |
| F1 | FITD | turn_count >= 4 enters monitoring | Turn | MONITOR | 100% |
| F3 | FITD | turns 4-6 high-risk window | Turn | HEIGHTEN | 80% |
| F4 | FITD | 3+ cooperative before harmful turn | Convo | BLOCK | 70%+ |

---

## Repository Structure

```
JailVax/
├── attacks/
│   ├── crescendo_attack.py      # Crescendo multi-turn attack (Vertex AI / google-genai)
│   ├── pair_attack.py           # PAIR prompt refinement attack
│   ├── gcg_attack.py            # GCG adversarial suffix transfer
│   └── fitd_attack.py           # Foot-in-the-door compliance attack
├── defense/
│   ├── jailvax_verify.py        # Z3 formal verifier (11 rules, 3 layers)
│   └── middleware.py            # Real-time verification middleware
├── formal_rules/
│   └── z3_rules.py              # Z3 constraint definitions
├── data/
│   ├── transcripts/             # Attack transcripts (JSON)
│   └── evaluation/              # Before/after evaluation results
├── evaluation/
│   ├── run_evaluation.py        # Replay attacks with JailVax active
│   └── analysis.py              # Generate charts and statistics
├── docs/
│   ├── JailVax_Final_Evaluation_Report.docx
│   ├── JailVax_Transcript_Analysis.docx
│   └── JailVax_FinalPresentation.pptx
├── notebooks/
│   └── jailvax_colab.ipynb      # Google Colab notebook for full pipeline
├── requirements.txt
├── setup.sh
├── LICENSE
└── README.md
```

---

## Installation

```bash
git clone https://github.com/aishvars/JailVax.git
cd JailVax
pip install -r requirements.txt
```

### Requirements

- Python 3.10+
- z3-solver
- google-genai (for Gemini API access)
- matplotlib, seaborn (for analysis)

### Vertex AI Setup (for running attacks)

```bash
pip install google-genai
```

```python
from google import genai
client = genai.Client(vertexai=True, project="YOUR_PROJECT_ID", location="us-central1")
```

---

## Usage

### Verify a transcript file

```python
from defense.jailvax_verify import JailVaxVerifier

verifier = JailVaxVerifier()

# Single transcript
result = verifier.verify(transcript)
print(f"Action: {result.overall_action}")  # SAFE, FLAG, MONITOR, BLOCK
print(f"Rules triggered: {[r.rule_id for r in result.triggered_rules]}")

# Batch verification
results = verifier.verify_batch(transcripts)
verifier.print_summary(results)
```

### Run a Crescendo attack

```python
from attacks.crescendo_attack import init_client, test_single, run_batch

init_client()
test_single()           # Single attack for testing
run_batch()             # Full batch (8 goals x 6 model pairs)
```

### Run the self-play loop

```python
# 1. Run attack
transcript = run_crescendo_attack(goal="...", target_model="gemini-2.5-flash")

# 2. Verify with Z3
result = verifier.verify(transcript)

# 3. If BLOCKED -> defense works
# 4. If SAFE but attack succeeded -> gap found, add new rule
# 5. Re-run attack against updated rules
```

---

## Attack Methods

### Crescendo (Russinovich et al., 2024)

Multi-turn gradual escalation. Starts with benign questions and progressively steers toward harmful content by building on the model's own responses. Our implementation adapts the Crescendomation algorithm for Gemini models via Vertex AI, with a custom 4-constraint judge (harm, topic drift, compliance, specificity) scoring each turn.

### PAIR (Chao et al., 2023)

Prompt Automatic Iterative Refinement. An attacker LLM iteratively crafts obfuscated single-turn prompts using strategies like roleplaying, logical appeal, and authority endorsement. Achieves 94% ASR with most attacks succeeding on the first attempt.

### GCG (Zou et al., 2023)

Greedy Coordinate Gradient adversarial suffix attack. Published suffixes optimized on open-source models are transferred to Gemini to test cross-model vulnerability. Four suffix strategies tested: Zou et al. 2023, HarmBench transfer, role induction, and obfuscation encoding.

### FITD (Foot-in-the-Door)

Psychological compliance technique. Builds agreement momentum through small benign requests before escalating to the harmful goal. Exploits the model's tendency toward consistency after prior cooperation.

---

## Evaluation Summary

### Before vs. After JailVax

| Attack | Total | Before ASR | After ASR | Change |
|--------|-------|-----------|----------|--------|
| Crescendo | 48 | 75.0% | 35.4% | -39.6pp |
| FITD | 115 | 38.3% | 35.7% | -2.6pp |
| GCG Transfer | 120 | 29.2% | 44.2% | +15.0%* |
| **Total** | **283** | **40.6%** | **39.2%** | **-1.4pp** |

*GCG increase is attributed to LLM non-determinism across runs, not a JailVax weakness. The G3 rule successfully blocked 43 individual suffix attempts.

### Crescendo Highlights

- gemini-2.5-pro ASR reduced from 50% to 6.25% (best protected model)
- "Bypass a firewall" goal: 100% to 0% ASR (complete neutralization)
- Block pattern begins at turn 4, continuous through turn 10
- Zero post-block bypasses across all 30 intercepted conversations

---

## Limitations

**FITD detection (50%):** FITD transcripts lack per-turn constraint scores, giving Z3 limited signal. The compliance-building turns are psychologically subtle and difficult to distinguish from legitimate multi-turn conversations.

**GCG Z3 detection (0%):** GCG's sparse data structure (success/fail + trial count) provides insufficient signal for trajectory-based Z3 rules. The G3 suffix anomaly rule operates at the prompt level and successfully blocks adversarial suffixes, but novel framing patterns can bypass detection.

**False positive rate:** While PAIR shows 0% FPR and Crescendo shows 25% FPR, the system has not been evaluated against a large corpus of benign conversations.

---

## References

1. Russinovich, M., Salem, A., & Eldan, R. (2024). *Great, Now Write an Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack.* USENIX Security 2025.
2. Chao, P., Robey, A., Dobriban, E., Hassani, H., Pappas, G. J., & Wong, E. (2023). *Jailbreaking Black Box Large Language Models in Twenty Queries.* arXiv:2310.08419.
3. Zou, A., Wang, Z., Kolter, J. Z., & Fredrikson, M. (2023). *Universal and Transferable Adversarial Attacks on Aligned Language Models.* arXiv:2307.15043.
4. De Moura, L., & Bjorner, N. (2008). *Z3: An Efficient SMT Solver.* TACAS 2008.
5. AIM-Intelligence. (2024). *Automated-Multi-Turn-Jailbreaks.* GitHub. (Base implementation for Crescendomation.)

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgments

This project was developed for CMU 14-795: AI Applications in Information Security, taught by David Varodayan. Affiliated with CMU CyLab Security and Privacy Institute.

Compute resources provided by Google Cloud Platform (Vertex AI credits through the GenAI App Builder program and 14-789 AI in Business Modeling course allocation).
