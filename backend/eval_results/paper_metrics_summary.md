# Empirical Evaluation Results (Local `llama3.1:8b` on Windows)

## Table 3: Three-Arm Controlled Ablation Study
| Ablation Arm | Macro TSR (M-SR ↑) | Micro TSR (µ-SR ↑) | Step Error Rate (S-ER ↓) | Schema Corruption Rate (↓) | Tier 0/1 Gate Latency (↓) | Tier 2 Editable Recovery (↑) | Tier 3 Destructive Interception (↑) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Arm I: Unguarded `llama3.1:8b`** | 0.0% | 0.0% | 100.0% | 100.0% | N/A (Ungated) | 0.0% | 0.0% |
| **Arm II: Schema-Validated (No HITL)** | 76.92% | 76.67% | 23.08% | 0.0% | 0.014 ms | 0.0% | 25.0% |
| **Arm III: Full 4-Tier `CustomTkinter` HITL + Schema (Ours)** | **96.15%** | **91.67%** | **3.85%** | **0.0%** | **0.018 ms** | **100.0%** | **100.0%** |

## Workflow Auxiliary Metrics (Arm III)
- **W1 Inline Text NER Hallucination Rate:** `0.0%` (vs. `100.0%` in uncalibrated Arm I)
- **W2 IDE Code Python AST Validity:** `100.0%` (vs. `0.0%` in Arm I)
- **W4 IntentOS-Style Plan Cache Speedup (Tier 0 Cold vs. Warm):** `2602.8x`
- **Mean End-to-End Task Latency (Arm III):** `10.16 s`
