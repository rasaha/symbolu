"""Pydantic request/response schemas for the v1 API."""

from __future__ import annotations

import datetime as dt
import re
import uuid

from pydantic import BaseModel, Field, field_validator

from ..domain.enums import AmbiguityResolution, BirthTimePrecision

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _Email(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v


# --- auth ------------------------------------------------------------------ #
class RegisterRequest(_Email):
    password: str = Field(min_length=10, max_length=256)


class RegisterResponse(BaseModel):
    user_id: uuid.UUID
    email: str


class LoginRequest(_Email):
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


# --- users ----------------------------------------------------------------- #
class UserMeResponse(BaseModel):
    id: uuid.UUID
    email: str
    status: str
    created_at: dt.datetime


# --- birth profiles -------------------------------------------------------- #
class BirthProfileCreateRequest(BaseModel):
    preferred_name: str = Field(min_length=1, max_length=120)
    birth_date: dt.date
    birth_time_local: dt.time | None = None
    birth_time_precision: BirthTimePrecision
    birthplace_label: str = Field(min_length=1, max_length=256)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    iana_timezone: str = Field(min_length=1, max_length=64)
    ambiguity_resolution: AmbiguityResolution | None = None
    # Required for APPROXIMATE precision (± minutes around the stated local time).
    uncertainty_minutes: int | None = Field(default=None, ge=1, le=720)


class UtcIntervalModel(BaseModel):
    start: dt.datetime
    end: dt.datetime


class BirthProfileResponse(BaseModel):
    id: uuid.UUID
    version: int
    preferred_name: str
    birth_date: dt.date
    birth_time_precision: BirthTimePrecision
    has_birth_time: bool
    birthplace_label: str
    iana_timezone: str
    utc_birth_instant: dt.datetime | None
    utc_interval: UtcIntervalModel | None
    uncertainty_minutes: int | None
    input_confidence: float


# --- natal (uncertainty-aware) --------------------------------------------- #
class ProvenanceModel(BaseModel):
    provider_id: str
    provider_version: str
    ephemeris_mode: str
    ayanamsa: str
    calculation_timestamp: dt.datetime
    numerical_precision_class: str
    fallback_used: bool
    fallback_reason: str | None
    input_confidence: float
    provider_kind: str
    synthetic_calculation: bool
    time_assumption: str | None = None


class FieldResultModel(BaseModel):
    """A derived Moon classification with an explicit certainty status."""

    status: str  # EXACT | STABLE | AMBIGUOUS | INDETERMINATE | UNAVAILABLE
    value: int | None = None
    name: str | None = None
    possible_values: list[int] | None = None
    possible_names: list[str] | None = None


class NatalMoonResponse(BaseModel):
    snapshot_id: uuid.UUID
    birth_profile_version: int
    birth_time_precision: str
    utc_interval: UtcIntervalModel
    moon_longitude_start: float
    moon_longitude_end: float | None
    moon_rashi: FieldResultModel
    moon_nakshatra: FieldResultModel
    moon_pada: FieldResultModel
    guna_eligibility: str
    # Provider safety surface (Area A): never present a synthetic result as authoritative.
    synthetic_calculation: bool
    authoritative: bool
    test_only: bool
    provenance: ProvenanceModel


# --- couples --------------------------------------------------------------- #
class InvitationCreateResponse(BaseModel):
    invitation_id: uuid.UUID
    token: str
    expires_at: dt.datetime


class MemberModel(BaseModel):
    user_id: uuid.UUID
    scope_slot: str
    status: str


class CoupleResponse(BaseModel):
    couple_id: uuid.UUID
    status: str
    members: list[MemberModel]


# --- consent / shared artifacts -------------------------------------------- #
class ConsentCreateRequest(BaseModel):
    couple_id: uuid.UUID
    artifact_type: str = Field(min_length=1, max_length=48)
    bounded_summary: str = Field(min_length=1, max_length=2000)
    purpose: str | None = Field(default=None, max_length=256)


class ConsentResponse(BaseModel):
    consent_event_id: uuid.UUID
    state: str
    source_scope: str
    created_at: dt.datetime


class SharedArtifactCreateRequest(BaseModel):
    consent_event_id: uuid.UUID
    payload_snapshot: str = Field(min_length=1, max_length=8000)


class SharedArtifactResponse(BaseModel):
    artifact_id: uuid.UUID
    artifact_type: str
    source_scope: str
    payload_snapshot: str
    created_at: dt.datetime
    provenance: dict


# --- secure chat (Phase 3A) ------------------------------------------------ #
# Client idempotency key: bounded, opaque, printable token chosen by the client.
_CLIENT_MESSAGE_ID_RE = r"^[A-Za-z0-9._:\-]{1,64}$"
# Mirrors Settings.chat_message_max_code_points (single source of truth); the
# service re-validates against configuration so the two never silently diverge.
_MESSAGE_BODY_MAX = 4000


class ConversationResponse(BaseModel):
    conversation_id: uuid.UUID
    couple_id: uuid.UUID
    status: str
    created_at: dt.datetime
    latest_sequence: int
    last_read_sequence: int
    member_user_ids: list[uuid.UUID]


class MessageCreateRequest(BaseModel):
    client_message_id: str = Field(pattern=_CLIENT_MESSAGE_ID_RE)
    body: str = Field(min_length=1, max_length=_MESSAGE_BODY_MAX)


class MessageResponse(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    sender_user_id: uuid.UUID
    client_message_id: str
    server_sequence: int
    # ``None`` for a tombstoned (deleted) message — metadata is retained, body is not.
    body: str | None
    created_at: dt.datetime
    deleted: bool
    deleted_at: dt.datetime | None


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    next_cursor: str | None
    has_more: bool


class ReadStateUpdateRequest(BaseModel):
    last_read_sequence: int = Field(ge=0)


class ReadStateResponse(BaseModel):
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    last_read_sequence: int
    updated_at: dt.datetime


# --- chat safety (Phase 3B) ------------------------------------------------- #
# Bounded, printable client idempotency key for reports (same shape as chat).
_CLIENT_REPORT_ID_RE = r"^[A-Za-z0-9._:\-]{1,64}$"
# Mirrors Settings.safety_report_description_max_code_points; the service
# re-validates against configuration so the two never silently diverge.
_REPORT_DESCRIPTION_MAX = 1000


class BlockCreateRequest(BaseModel):
    blocked_user_id: uuid.UUID


class BlockResponse(BaseModel):
    block_id: uuid.UUID
    blocked_user_id: uuid.UUID
    status: str
    created_at: dt.datetime
    revoked_at: dt.datetime | None


class BlockListResponse(BaseModel):
    blocks: list[BlockResponse]


class ReportCreateRequest(BaseModel):
    conversation_id: uuid.UUID
    target_type: str
    target_message_id: uuid.UUID | None = None
    reason: str
    # SENSITIVE: stored on the report row only; never echoed back, logged,
    # audited, or copied into evidence/case events.
    description: str | None = Field(default=None, max_length=_REPORT_DESCRIPTION_MAX)
    client_report_id: str = Field(pattern=_CLIENT_REPORT_ID_RE)


class ReportResponse(BaseModel):
    """Reporter-visible acknowledgement only (DILCHAT-D3B-5).

    Deliberately carries NO description echo, NO internal case id, NO case
    state, and NO evidence — those live behind the INTERNAL safety boundary.
    """

    report_id: uuid.UUID
    conversation_id: uuid.UUID
    target_type: str
    target_message_id: uuid.UUID | None
    reason: str
    status: str
    created_at: dt.datetime


class ReportListResponse(BaseModel):
    reports: list[ReportResponse]
