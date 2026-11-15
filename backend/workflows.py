import ast
import json
import re
import subprocess
from typing import Any, Dict
import requests
from ddgs import DDGS

from cache import StateStore
from hitl_ui import HITLManager
from schemas import OSToolCallContract, SecurityTier, classify_deterministic_tier

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "llama3.1:8b"


def _call_ollama(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    num_predict: int = 1024,
    json_mode: bool = False,
) -> str:
    payload: Dict[str, Any] = {
        "model": MODEL_NAME,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": temperature,
            "top_k": 1 if temperature == 0.0 else 40,
            "num_predict": num_predict,
        },
    }
    if json_mode:
        payload["format"] = "json"

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Ollama is not reachable on http://127.0.0.1:11434. Start Ollama first."
        ) from exc


def run_inline_text(prompt: str, selected_text: str, store: StateStore) -> Dict[str, Any]:
    """Workflow 1: Air-gapped greedy text formatting/refinement + entity check."""
    raw_source = (selected_text or prompt).replace("\r\n", "\n").replace("\r", "\n")
    # Collapse single line-wraps from Word/PDF selections while preserving paragraph breaks
    source = re.sub(r"(?<!\n)\n(?!\n)", " ", raw_source).strip()
    max_tokens = max(80, int(len(source.split()) * 2.4))

    system = (
        "You are a precise inline text editor. Apply ONLY the user's formatting or grammar "
        "instruction to the provided text using strictly the facts present in the text. "
        "Rules:\n"
        "1. Do NOT add new facts, examples, or introductory/closing labels.\n"
        "2. Do NOT wrap output in ``` code blocks or start with a colon.\n"
        "3. If the user asks for 'points' or a 'list', format EVERY point consistently "
        "on its own line starting with '- ' (never mix '-' and '1.'), with no mid-sentence line breaks."
    )
    user_msg = f"Instruction: {prompt}\n\nText:\n{source}"
    output = _call_ollama(system, user_msg, temperature=0.0, num_predict=max_tokens)

    # Strip accidental labels, leading colons, or triple-backtick fences
    output = re.sub(
        r"^(Here (is|are)[^:\n]*:|Refined[^:\n]*:|Output[^:\n]*:)\s*",
        "",
        output,
        flags=re.IGNORECASE,
    ).lstrip(": ").strip()
    output = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", output).strip()

    # Lightweight proper-noun hallucination check
    in_entities = set(re.findall(r"\b[A-Z][a-zA-Z0-9]{2,}\b", source))
    out_entities = set(re.findall(r"\b[A-Z][a-zA-Z0-9]{2,}\b", output))
    novel_entities = sorted(out_entities - in_entities)

    store.append_audit("inline_text", 0, prompt, "[CLIPBOARD_TRANSFORM]", "executed")
    return {
        "status": "executed",
        "workflow": "inline_text",
        "output": output,
        "novel_entities_warning": novel_entities,
    }

def run_ide_code(prompt: str, selected_text: str, store: StateStore) -> Dict[str, Any]:
    """Workflow 2: Air-gapped IDE code refactoring/generation with AST check."""
    system = (
        "You are an expert software engineer. Fulfill the coding instruction concisely. "
        "If code is provided, return ONLY the updated code without markdown backticks or chatter."
    )
    user_msg = (
        f"Instruction: {prompt}\n\nCode Context:\n{selected_text}"
        if selected_text
        else prompt
    )
    output = _call_ollama(system, user_msg, temperature=0.1, num_predict=2048)

    # Strip accidental markdown code fences if emitted
    output = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", output).strip()

    ast_valid = True
    try:
        ast.parse(output)
    except SyntaxError:
        ast_valid = False

    store.append_audit("ide_code", 0, prompt, "[CODE_TRANSFORM]", "executed")
    return {
        "status": "executed",
        "workflow": "ide_code",
        "output": output,
        "python_ast_valid": ast_valid,
    }


def run_web_qa(prompt: str, selected_text: str, store: StateStore) -> Dict[str, Any]:
    """Workflow 3: Opt-in outbound web retrieval + grounded local synthesis."""
    query = f"{prompt} {selected_text}".strip()
    snippets = []
    try:
        with DDGS() as ddgs:
            for idx, r in enumerate(ddgs.text(query, max_results=4), start=1):
                snippets.append(
                    f"[{idx}] {r.get('title', '')}: {r.get('body', '')} ({r.get('href', '')})"
                )
    except Exception as exc:
        return {"status": "error", "workflow": "web_qa", "output": f"Search failed: {exc}"}

    context_block = "\n".join(snippets) if snippets else "No external results retrieved."
    system = (
        "Answer the user's question using ONLY the retrieved web snippets below. "
        "You MUST attach inline bracketed source numbers like [1] or [2] at the end of every factual sentence. "
        "If the snippets do not contain the answer, state that clearly without guessing."
    )
    user_msg = f"Question: {query}\n\nRetrieved Context:\n{context_block}"
    answer = _call_ollama(system, user_msg, temperature=0.1, num_predict=1024)

    store.append_audit("web_qa", 0, query, "[WEB_RETRIEVAL]", "executed")
    return {
        "status": "executed",
        "workflow": "web_qa",
        "output": answer,
        "sources": snippets,
    }


def run_os_powershell(
    prompt: str, hitl: HITLManager, store: StateStore
) -> Dict[str, Any]:
    """Workflow 4: Cached or Pydantic-validated PowerShell + 4-Tier HITL Gate."""
    cached_cmd = store.lookup_cached_command(prompt)
    cache_hit = cached_cmd is not None

    if cache_hit:
        ps_cmd = cached_cmd
    else:
        system = (
            "You are a Windows PowerShell automation planner. Translate the user's request "
            "into a SINGLE, self-contained, non-interactive PowerShell command.\n"
            "Rules:\n"
            "1. Always include ALL required parameters and values directly inside 'powershell_command' "
            "(never omit -Path, and always add -Force to New-Item -ItemType Directory).\n"
            "2. For 'top N' queries, always pipe to Sort-Object and Select-Object -First N.\n"
            "3. Respond ONLY with a JSON object matching the examples below.\n\n"
            "Example 1 (Top processes):\n"
            '{"thought": "Sort processes by CPU descending and take top 5", '
            '"cmdlet_verb": "Get", '
            '"powershell_command": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5", '
            '"args_map": {}, "status": "FINISH"}\n\n'
            "Example 2 (Create directory):\n"
            '{"thought": "Create target directory idempotently", '
            '"cmdlet_verb": "New", '
            '"powershell_command": "New-Item -ItemType Directory -Force -Path \'C:\\\\Temp\\\\Demo\'", '
            '"args_map": {"Path": "C:\\\\Temp\\\\Demo"}, "status": "FINISH"}'
        )
        raw_json = _call_ollama(
            system, prompt, temperature=0.0, num_predict=512, json_mode=True
        )
        contract = OSToolCallContract.model_validate(json.loads(raw_json))
        ps_cmd = contract.powershell_command

    tier = classify_deterministic_tier(ps_cmd)
    approved, final_cmd = hitl.request_approval(
        tier=int(tier), intent=prompt, command=ps_cmd
    )

    if not approved:
        store.append_audit("os_powershell", int(tier), prompt, ps_cmd, "denied")
        return {
            "status": "denied",
            "workflow": "os_powershell",
            "tier": int(tier),
            "cache_hit": cache_hit,
            "output": "Action denied or timed out in HITL security gate.",
        }

    # Re-verify tier if user edited the command in Tier 2 modal
    if final_cmd != ps_cmd:
        rechecked_tier = classify_deterministic_tier(final_cmd)
        if rechecked_tier == SecurityTier.TIER_3_DESTRUCTIVE:
            approved_t3, final_cmd = hitl.request_approval(
                tier=int(rechecked_tier), intent=prompt, command=final_cmd
            )
            if not approved_t3:
                store.append_audit(
                    "os_powershell", int(rechecked_tier), prompt, final_cmd, "denied"
                )
                return {
                    "status": "denied",
                    "workflow": "os_powershell",
                    "tier": int(rechecked_tier),
                    "cache_hit": cache_hit,
                    "output": "Edited command escalated to Tier 3 and was denied.",
                }

    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", final_cmd],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
    )
    status_str = "executed" if completed.returncode == 0 else "error"
    store.append_audit("os_powershell", int(tier), prompt, final_cmd, status_str)

    if completed.returncode == 0 and not cache_hit and tier in (
        SecurityTier.TIER_0_READ_ONLY,
        SecurityTier.TIER_1_REVERSIBLE,
    ):
        store.store_cached_command(prompt, final_cmd)

    output_text = (
        completed.stdout.strip()
        or completed.stderr.strip()
        or "(Command completed with no output)"
    )
    return {
        "status": status_str,
        "workflow": "os_powershell",
        "tier": int(tier),
        "cache_hit": cache_hit,
        "executed_command": final_cmd,
        "output": output_text,
    }