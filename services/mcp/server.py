"""
ReVoice MCP Server — Model Context Protocol over HTTP (JSON-RPC 2.0).

Implements the MCP streamable-HTTP transport without an external mcp package,
keeping the project's pinned pydantic version intact.

Transport: POST /mcp
  - initialize        → server capabilities + tool list
  - tools/list        → tool schemas
  - tools/call        → execute a memory tool

Any MCP-compatible client (Qwen agent, Claude Desktop via proxy, etc.) can
connect to this endpoint and call the four memory tools below.

Tools exposed:
  search_memories      — keyword search over a user's personal concepts
  get_concept_details  — full detail + relationships for one concept
  get_cue_preferences  — learned cue strategy scores for a user/category
  get_user_progress    — all concept ability states for a user
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from packages.schemas.db import SessionLocal
from packages.schemas.models import (
    Concept, Relationship, AbilityState, CuePreference,
)

router = APIRouter()

# ─── Tool definitions (MCP tool schema format) ───────────────────────────────

_TOOLS = [
    {
        "name": "search_memories",
        "description": (
            "Search a user's personal memory concepts by keyword. "
            "Returns matching active concepts with category and concept_id. "
            "Use this to discover what memories exist for a user before calling "
            "get_concept_details for a specific one."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner_id": {
                    "type": "string",
                    "description": "User id (e.g. 'margaret', 'james').",
                },
                "query": {
                    "type": "string",
                    "description": "Keyword to match against concept label or category.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Max results to return (default 5).",
                    "default": 5,
                },
            },
            "required": ["owner_id", "query"],
        },
    },
    {
        "name": "get_concept_details",
        "description": (
            "Get full detail for one personal memory concept: label, category, "
            "relationship context (e.g. 'grandchild_of'), and current ability state. "
            "Use after search_memories to inspect a specific concept."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept_id": {
                    "type": "string",
                    "description": "The concept_id as returned by search_memories.",
                },
            },
            "required": ["concept_id"],
        },
    },
    {
        "name": "get_cue_preferences",
        "description": (
            "Get learned cue strategy preferences for a user in a concept category. "
            "Returns strategies ranked by success score — these bias Qwen's cue-bank "
            "generation so future hints use what worked before."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner_id": {
                    "type": "string",
                    "description": "User id.",
                },
                "category": {
                    "type": "string",
                    "description": "Concept category: person, document, order, place, medication, event.",
                },
            },
            "required": ["owner_id", "category"],
        },
    },
    {
        "name": "get_user_progress",
        "description": (
            "Get all concept ability states for a user. Shows which concepts need "
            "more practice (assistance_level 4 = full reveal required) vs. those "
            "recalled with minimal help (level 1-2)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner_id": {
                    "type": "string",
                    "description": "User id.",
                },
            },
            "required": ["owner_id"],
        },
    },
]

# ─── Tool implementations ─────────────────────────────────────────────────────

def _search_memories(owner_id: str, query: str, top_k: int = 5) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Concept)
            .filter(Concept.owner_id == owner_id, Concept.status == "active")
            .all()
        )
        q = query.lower()
        matches = [
            {"concept_id": r.id, "label": r.label, "category": r.category}
            for r in rows
            if q in r.label.lower() or q in r.category.lower()
        ]
        return matches[:top_k]
    finally:
        db.close()


def _get_concept_details(concept_id: str) -> dict:
    db = SessionLocal()
    try:
        concept = db.query(Concept).filter(Concept.id == concept_id).first()
        if not concept:
            return {"error": f"concept '{concept_id}' not found"}

        rels = (
            db.query(Relationship)
            .filter(Relationship.from_concept_id == concept_id)
            .all()
        )
        ability = db.query(AbilityState).filter(AbilityState.concept_id == concept_id).first()

        return {
            "concept_id": concept.id,
            "label": concept.label,
            "category": concept.category,
            "sensitivity": concept.sensitivity,
            "status": concept.status,
            "relationships": [
                {"relation_type": r.relation_type, "to_concept_id": r.to_concept_id}
                for r in rels
            ],
            "ability_state": {
                "assistance_level": ability.assistance_level,
                "uncertainty": ability.uncertainty,
            } if ability else None,
        }
    finally:
        db.close()


def _get_cue_preferences(owner_id: str, category: str) -> list[dict]:
    db = SessionLocal()
    try:
        prefs = (
            db.query(CuePreference)
            .filter(
                CuePreference.owner_id == owner_id,
                CuePreference.category == category,
            )
            .order_by(CuePreference.score.desc())
            .limit(5)
            .all()
        )
        return [
            {
                "strategy": p.strategy,
                "score": p.score,
                "successes": p.successes,
                "failures": p.failures,
                "success_rate": round(p.successes / max(1, p.successes + p.failures), 3),
            }
            for p in prefs
        ]
    finally:
        db.close()


def _get_user_progress(owner_id: str) -> list[dict]:
    db = SessionLocal()
    try:
        concepts = (
            db.query(Concept)
            .filter(Concept.owner_id == owner_id, Concept.status == "active")
            .all()
        )
        concept_map = {c.id: c for c in concepts}
        abilities = (
            db.query(AbilityState)
            .filter(AbilityState.concept_id.in_(list(concept_map.keys())))
            .all()
        )
        return [
            {
                "concept_id": a.concept_id,
                "label": concept_map[a.concept_id].label,
                "category": concept_map[a.concept_id].category,
                "assistance_level": a.assistance_level,
                "uncertainty": a.uncertainty,
            }
            for a in abilities
            if a.concept_id in concept_map
        ]
    finally:
        db.close()


_TOOL_DISPATCH = {
    "search_memories": lambda args: _search_memories(**args),
    "get_concept_details": lambda args: _get_concept_details(**args),
    "get_cue_preferences": lambda args: _get_cue_preferences(**args),
    "get_user_progress": lambda args: _get_user_progress(**args),
}

# ─── MCP JSON-RPC 2.0 endpoint ────────────────────────────────────────────────

def _ok(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _err(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


@router.post("", summary="MCP JSON-RPC 2.0 endpoint")
async def mcp_endpoint(request: Request) -> JSONResponse:
    """
    MCP-compatible HTTP endpoint (streamable-HTTP transport).

    Clients send JSON-RPC 2.0 messages. Supported methods:
    - initialize           → returns server info and capabilities
    - notifications/initialized  → acknowledged (no response body)
    - tools/list           → returns all tool schemas
    - tools/call           → executes a memory tool

    See https://modelcontextprotocol.io for the full protocol specification.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            _err(None, -32700, "Parse error: request body must be JSON"),
            status_code=400,
        )

    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    # Notifications have no id and expect no response
    if method.startswith("notifications/"):
        return JSONResponse({}, status_code=202)

    if method == "initialize":
        return JSONResponse(_ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "ReVoice Memory Agent",
                "version": "1.0.0",
                "description": (
                    "Persistent adaptive memory store for word-finding assistance. "
                    "Exposes personal concept search, relationship context, learned "
                    "cue preferences, and per-concept ability states as MCP tools."
                ),
            },
        }))

    if method == "tools/list":
        return JSONResponse(_ok(req_id, {"tools": _TOOLS}))

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        handler = _TOOL_DISPATCH.get(tool_name)
        if not handler:
            return JSONResponse(
                _err(req_id, -32602, f"Unknown tool: '{tool_name}'"),
                status_code=400,
            )
        try:
            result = handler(arguments)
            return JSONResponse(_ok(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": False,
            }))
        except TypeError as exc:
            return JSONResponse(
                _err(req_id, -32602, f"Invalid arguments for '{tool_name}': {exc}"),
                status_code=400,
            )
        except Exception as exc:
            return JSONResponse(
                _err(req_id, -32603, f"Tool execution error: {exc}"),
                status_code=500,
            )

    return JSONResponse(
        _err(req_id, -32601, f"Method not found: '{method}'"),
        status_code=404,
    )


@router.get("", summary="MCP server info")
async def mcp_info() -> dict:
    """Returns MCP server metadata and available tool names for quick discovery."""
    return {
        "server": "ReVoice Memory Agent MCP Server",
        "protocol": "MCP JSON-RPC 2.0 (streamable-HTTP transport)",
        "endpoint": "POST /mcp",
        "tools": [t["name"] for t in _TOOLS],
        "spec": "https://modelcontextprotocol.io",
    }
