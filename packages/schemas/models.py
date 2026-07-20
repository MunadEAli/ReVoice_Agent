import json
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Text, Float, ForeignKey
)
from packages.schemas.db import Base


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Text, primary_key=True)
    label = Column(Text, nullable=False)
    category = Column(Text, nullable=False)         # person | document | order | place | event
    media_url = Column(Text, nullable=True)
    owner_id = Column(Text, nullable=False)
    sensitivity = Column(Text, default="normal")
    status = Column(Text, default="active")         # active | superseded
    superseded_by = Column(Text, nullable=True)
    created_at = Column(Text, default=_now)
    updated_at = Column(Text, default=_now)


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Text, primary_key=True)
    from_concept_id = Column(Text, ForeignKey("concepts.id"), nullable=False)
    to_concept_id = Column(Text, ForeignKey("concepts.id"), nullable=False)
    relation_type = Column(Text, nullable=False)    # grandchild_of, located_at, etc.
    provenance = Column(Text, nullable=False)       # user | caregiver | system
    status = Column(Text, default="active")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False)
    mode = Column(Text, nullable=False)             # practice | live | preparation | review
    started_at = Column(Text, default=_now)
    ended_at = Column(Text, nullable=True)


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Text, primary_key=True)
    session_id = Column(Text, ForeignKey("sessions.id"), nullable=False)
    concept_id = Column(Text, ForeignKey("concepts.id"), nullable=True)
    input_modalities = Column(Text, default="[]")   # json array
    context = Column(Text, nullable=True)
    candidate_concept_ids = Column(Text, default="[]")   # json array ranked
    candidate_scores = Column(Text, default="[]")        # json array of score breakdowns
    confirmed_concept_id = Column(Text, nullable=True)
    outcome = Column(Text, nullable=True)           # confirmed | rejected | none_of_these
    response_latency_ms = Column(Integer, nullable=True)
    created_at = Column(Text, default=_now)


class CueEvent(Base):
    __tablename__ = "cue_events"

    id = Column(Text, primary_key=True)
    attempt_id = Column(Text, ForeignKey("attempts.id"), nullable=False)
    rung = Column(Integer, nullable=False)           # 1..4
    cue_type = Column(Text, nullable=False)
    cue_content = Column(Text, nullable=True)
    outcome = Column(Text, nullable=True)            # no_retrieval | partial_retrieval | successful
    order_index = Column(Integer, nullable=False, default=0)


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(Text, primary_key=True)
    target_type = Column(Text, nullable=False)      # concept | relationship
    target_id = Column(Text, nullable=False)
    before_value = Column(Text, nullable=True)
    after_value = Column(Text, nullable=True)
    actor = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(Text, default=_now)


class AbilityState(Base):
    __tablename__ = "ability_states"

    concept_id = Column(Text, ForeignKey("concepts.id"), primary_key=True)
    assistance_level = Column(Integer, nullable=False, default=4)  # 1=low help, 4=reveal
    uncertainty = Column(Float, nullable=False, default=0.5)
    recent_contexts = Column(Text, default="[]")    # json array, cleared after 2 distinct successes
    last_observed = Column(Text, nullable=True)


class CuePreference(Base):
    __tablename__ = "cue_preferences"

    id = Column(Text, primary_key=True)
    owner_id = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    strategy = Column(Text, nullable=False)
    successes = Column(Integer, nullable=False, default=0)
    failures = Column(Integer, nullable=False, default=0)
    score = Column(Float, nullable=False, default=0.0)
    last_outcome = Column(Text, nullable=True)
    updated_at = Column(Text, default=_now)


class AccessPolicy(Base):
    __tablename__ = "access_policies"

    id = Column(Text, primary_key=True)
    subject = Column(Text, nullable=False)          # role or user id
    resource_scope = Column(Text, nullable=False)   # concept category or 'all'
    operation = Column(Text, nullable=False)        # read | write | export
    allow = Column(Integer, nullable=False, default=1)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Text, primary_key=True)
    event_type = Column(Text, nullable=False)       # retrieval | tool_call | confirmation | correction
    payload = Column(Text, nullable=True)           # json, includes full score breakdowns
    actor = Column(Text, nullable=True)
    created_at = Column(Text, default=_now)
