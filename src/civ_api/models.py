"""Pydantic response/request models for the CI-V Explorer API."""

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# CI-V command and sub-command codes are short hex strings (e.g. "05", "1A").
# We accept 1-4 hex chars, case-insensitive, so "05", "1a", "0A" all pass.
# This also rejects anything with spaces, quotes, angle brackets, scripts, etc.
_HEX_CMD_RE = r"^[0-9A-Fa-f]{1,4}$"


class RadioSummary(BaseModel):
    """Top-level radio descriptor (used in list and detail responses)."""

    id: str = Field(..., description="Short radio id, e.g. '7300'")
    name: str = Field(..., description="Model name, e.g. 'IC-7300'")
    address: str = Field(..., description="Default CI-V transceiver address (hex, no 0x)")
    command_count: int = Field(..., description="Number of CI-V command rows loaded for this radio")


class Capability(BaseModel):
    """A single radio capability with per-radio support values."""

    name: str
    description: str
    command_evidence: str
    radios: dict[str, Union[bool, str]]


class Command(BaseModel):
    """A single CI-V command row parsed from a radio's command table CSV."""

    radio_id: str
    cmd: str = Field(..., description="Primary command hex (e.g. '05')")
    sub_cmd: str = Field("", description="Sub-command hex (e.g. '00'); empty if none")
    data: str = Field("", description="Data payload description from the manual")
    description: str = Field("", description="Human-readable command description")


class CommandListResponse(BaseModel):
    """Paginated command listing."""

    radio_id: Optional[str] = None
    query: Optional[str] = None
    total: int
    limit: int
    offset: int
    items: list[Command]


class FeedbackSubmission(BaseModel):
    """User-submitted correction or comment on a command entry.

    The API is read-only; this is the one write path. Submissions are stored
    locally (JSONL) for later review and do not mutate the reference data.

    All free-text fields are length-capped to prevent abuse and to keep the
    JSONL append log manageable. Cmd/sub_cmd are constrained to short hex
    strings so no markup or script can be submitted through them. The
    ``field`` value is an enum so attackers cannot invent field names.
    """

    radio_id: str = Field(..., max_length=16, description="Radio id the feedback concerns")
    cmd: str = Field("", max_length=8, pattern=r"^$|^[0-9A-Fa-f]{1,4}$", description="Primary command hex; empty or 1-4 hex chars (blank for capability feedback)")
    sub_cmd: str = Field("", max_length=8, pattern=r"^$|^[0-9A-Fa-f]{1,4}$", description="Sub-command hex; empty or 1-4 hex chars")
    field: Literal["cmd", "sub_cmd", "data", "description", "capability"] = Field(
        ..., description="Which field is wrong"
    )
    capability_name: str = Field("", max_length=64, description="Name of the capability being corrected (when field is 'capability')")
    suggested_value: str = Field(..., max_length=500, description="Corrected value for the field")
    notes: str = Field("", max_length=2000, description="Free-text explanation or evidence")
    submitter: str = Field("", max_length=100, description="Optional submitter handle/email")


class FeedbackAck(BaseModel):
    id: str
    status: str = Field(..., description="One of: 'received'")
    received_at: str