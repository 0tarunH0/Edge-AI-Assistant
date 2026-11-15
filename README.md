# Local-First Edge AI Desktop Assistant (Windows)

A privacy-preserving, user-space Windows AI desktop assistant powered by local `llama3.1:8b` via Ollama, orchestrated with FastAPI/Uvicorn, triggered system-wide via AutoHotkey v2.0 (`Ctrl+Shift+X`), and protected by a 4-tier `CustomTkinter` Human-in-the-Loop (HITL) security gate.

## Features & Workflows

1. **Inline Text Formatting (`W1`):** Greedy decoding (`T=0.0`) with proper-noun entity drift verification and in-place clipboard replacement.
2. **IDE Code Assistance (`W2`):** Low-temperature code refactoring with Python AST (`ast.parse`) syntax verification.
3. **Web-Augmented Q&A (`W3`):** Opt-in outbound web retrieval via `ddgs` with mandatory inline `[1]`, `[2]` source citations.
4. **OS Task Automation (`W4`):** Pydantic-validated PowerShell generation with an IntentOS-style SQLite plan cache, SHA-256 hash-chained audit logging, and a 4-tier `CustomTkinter` security gate:
   - **Tier 0 (Read-Only) & Tier 1 (Reversible):** Auto-execute with audit logging (`0.018 ms` gate overhead).
   - **Tier 2 (Privileged):** Amber modal with an editable PowerShell command payload and 15s auto-deny timer.
   - **Tier 3 (Destructive):** Crimson modal with a read-only payload lock and typed `CONFIRM` gate.

## Empirical Ablation Results (`llama3.1:8b`)

| Ablation Arm | Macro TSR (M-SR ↑) | Micro TSR (µ-SR ↑) | Step Error Rate (S-ER ↓) | Schema Corruption (↓) | Tier 0/1 Gate Latency (↓) | Tier 2 Edit Recovery (↑) | Tier 3 Interception (↑) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Arm I: Unguarded `llama3.1:8b`** | 0.0% | 0.0% | 100.0% | 100.0% | N/A | 0.0% | 0.0% |
| **Arm II: Schema-Validated (No HITL)** | 76.92% | 76.67% | 23.08% | 0.0% | 0.014 ms | 0.0% | 25.0% |
| **Arm III: Full 4-Tier HITL + Schema (Ours)** | **96.15%** | **91.67%** | **3.85%** | **0.0%** | **0.018 ms** | **100.0%** | **100.0%** |

- **W1 Inline Text NER Hallucination Rate:** `0.0%` (vs. `100.0%` unguarded)
- **W2 IDE Code Python AST Validity:** `100.0%` (vs. `0.0%` unguarded)
- **W4 User-Space Plan Cache Speedup (Tier 0 Cold vs. Warm):** `2602.8x`
- **Mean End-to-End Task Latency (Arm III):** `10.16 s`

## Project Structure

```text
edge-ai-assistant/
├── backend/
│   ├── requirements.txt
│   ├── schemas.py          # Pydantic contracts & deterministic 0-3 risk classifier
│   ├── hitl_ui.py          # 4-tier CustomTkinter HITL security modals
│   ├── cache.py            # SQLite plan cache & SHA-256 hash-chained audit log
│   ├── workflows.py        # Ollama (llama3.1:8b) handlers for W1-W4
│   ├── main.py             # FastAPI server + CustomTkinter mainloop bridge
│   ├── eval_runner.py      # Automated 3-arm ablation benchmark suite
│   └── eval_results/       # Exported JSON logs and Markdown summary tables
└── client/
    └── assistant.ahk       # AutoHotkey v2.0 global hotkey client (Ctrl+Shift+X)

```

## Quickstart

1. **Pull the local model in Ollama:**
```powershell
ollama pull llama3.1:8b

```


2. **Install backend dependencies and start the server:**
```powershell
cd backend
pip install -r requirements.txt
python main.py

```


3. **Launch the global hotkey client:**
Double-click `client/assistant.ahk` (requires AutoHotkey v2.0) and press `Ctrl+Shift+X` in any Windows application.
4. **Run the automated 3-arm ablation benchmark:**
```powershell
cd backend
python eval_runner.py

```
