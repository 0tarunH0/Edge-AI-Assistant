import re
from enum import IntEnum
from typing import Any, Dict, Literal
from pydantic import BaseModel, Field, field_validator


class SecurityTier(IntEnum):
    TIER_0_READ_ONLY = 0     # Auto-execute + Audit Log
    TIER_1_REVERSIBLE = 1    # Auto-execute + Audit Log
    TIER_2_PRIVILEGED = 2    # CustomTkinter Editable Modal + 15s Auto-Deny Timer
    TIER_3_DESTRUCTIVE = 3   # CustomTkinter Read-Only Lock + Typed CONFIRM Gate


DESTRUCTIVE_PATTERNS = re.compile(
    r"\b(Remove-Item|del|rm|rmdir|Format-Volume|Clear-Disk|Stop-Process|kill|"
    r"Clear-EventLog|Reset-ComputerMachinePassword|Invoke-Expression|iex)\b",
    re.IGNORECASE,
)

PRIVILEGED_PATTERNS = re.compile(
    r"\b(Set-ExecutionPolicy|New-Service|Stop-Service|Restart-Service|Set-ItemProperty|"
    r"reg\s+add|reg\s+delete|netsh|New-NetFirewallRule|Start-Process\s+.*-Verb\s+RunAs)\b",
    re.IGNORECASE,
)

READ_ONLY_VERBS = {
    "Get", "Select", "Measure", "Test", "Find", "Search", "Resolve", "Compare"
}


class InvokeRequest(BaseModel):
    workflow: Literal["inline_text", "ide_code", "web_qa", "os_powershell"]
    prompt: str = Field(..., min_length=1, max_length=4000)
    selected_text: str = Field(default="", max_length=16000)


class OSToolCallContract(BaseModel):
    thought: str = Field(..., max_length=280)
    cmdlet_verb: str = Field(..., pattern=r"^[A-Z][a-zA-Z0-9-]+$")
    powershell_command: str = Field(..., min_length=2, max_length=1024)
    args_map: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["CONTINUE", "FINISH"]

    @field_validator("powershell_command")
    @classmethod
    def block_obfuscation_and_smuggling(cls, v: str) -> str:
        if any(ord(ch) in (0x200B, 0xFEFF, 0x202E) for ch in v):
            raise ValueError("Zero-width Unicode steganography detected; failing closed.")
        if "-EncodedCommand" in v or "-enc " in v.lower():
            raise ValueError("Base64 encoded PowerShell commands are prohibited.")
        return v.strip()


def classify_deterministic_tier(command: str) -> SecurityTier:
    """Assigns HITL security tier deterministically via regex/verb inspection."""
    if DESTRUCTIVE_PATTERNS.search(command):
        return SecurityTier.TIER_3_DESTRUCTIVE
    if PRIVILEGED_PATTERNS.search(command):
        return SecurityTier.TIER_2_PRIVILEGED
    first_token = command.strip().split()[0]
    verb = first_token.split("-")[0] if "-" in first_token else ""
    if verb in READ_ONLY_VERBS and "|" not in command and ">" not in command:
        return SecurityTier.TIER_0_READ_ONLY
    return SecurityTier.TIER_1_REVERSIBLE