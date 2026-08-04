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
    input_confidence: float


# --- natal ----------------------------------------------------------------- #
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
    time_assumption: str | None = None


class NatalMoonResponse(BaseModel):
    snapshot_id: uuid.UUID
    birth_profile_version: int
    moon_longitude: float
    rashi_index: int
    rashi_name: str
    nakshatra_index: int
    nakshatra_name: str
    pada: int
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
