"""Phase 10IN - focused provenance source-envelope validator tests.

These tests prove the minimum runtime behavior specified by 10IL:
the ``provenance_commitment`` becomes the deterministic SHA-256 commitment of
the exact canonical disclosed provenance source envelope, with a raw JSON
parsing boundary that rejects duplicate keys.

They are deliberately NOT a verifier-over-verifier suite. Small, direct,
structural tests for the newly-added binding.
"""

from __future__ import annotations

import hashlib
import json

import pytest

import backend.world.local_first_pair_provenance_envelope as pv

SCHEMA = "first_provenance_envelope.1"
DOMAIN = "GENESIS_FIRST_PAIR_PROVENANCE_V1"


def _material(canonical_name: str = "Adam") -> dict:
    return {
        "canonical_name": canonical_name,
        "source_artifact_id": "genesis-source-identity-v1",
        "source_artifact_integrity_id": "d" * 64,
        "operator_approval_ref": "operator-approval-0001",
    }


def _envelope(canonical_name: str = "Adam", timestamp: str = "2026-08-23T00:00:00Z") -> dict:
    return {
        "source_envelope_schema_version": SCHEMA,
        "domain_separator": DOMAIN,
        "source_ref": "genesis.canonical.identity.source",
        "source_timestamp": timestamp,
        "provenance_material": _material(canonical_name),
    }


def _raw(envelope: dict) -> bytes:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _commitment(envelope: dict) -> str:
    mat = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(mat.encode("utf-8")).hexdigest()


def test_valid_adam_envelope_binds_commitment():
    envelope = _envelope("Adam")
    result = pv.validate_provenance_source_envelope(_raw(envelope), _commitment(envelope))
    assert result["ok"] is True
    assert result["envelope_valid"] is True
    assert result["commitment_matches"] is True
    assert result["canonical_name"] == "Adam"


def test_valid_eve_envelope_binds_commitment():
    # Two separate envelopes: canonical_name is singular Adam|Eve (10IL §F).
    envelope = _envelope("Eve")
    result = pv.validate_provenance_source_envelope(_raw(envelope), _commitment(envelope))
    assert result["ok"] is True
    assert result["canonical_name"] == "Eve"
    assert result["derived_commitment"] == _commitment(envelope)


def test_tamper_changes_commitment_and_fails_closed():
    envelope = _envelope("Adam")
    tampered = dict(envelope)
    material = dict(envelope["provenance_material"])
    material["source_artifact_id"] = "different-source-v2"
    tampered["provenance_material"] = material
    correct = _commitment(envelope)
    assert _commitment(tampered) != correct
    result = pv.validate_provenance_source_envelope(_raw(tampered), correct)
    assert result["ok"] is False
    assert result["commitment_matches"] is False


def test_duplicate_json_key_rejected_at_raw_boundary():
    # Standard json.load would silently collapse the duplicate; the raw
    # boundary must reject it (10IL §H).
    text = (
        '{"source_envelope_schema_version":"%s",'
        '"source_envelope_schema_version":"%s"}' % (SCHEMA, SCHEMA)
    )
    result = pv.validate_provenance_source_envelope(text.encode("utf-8"), "0" * 64)
    assert result["ok"] is False
    assert "duplicate key" in result["error"]


def test_non_hex_proposed_commitment_rejected():
    envelope = _envelope("Eve")
    result = pv.validate_provenance_source_envelope(_raw(envelope), "NOTHEX")
    assert result["ok"] is False
    assert result["commitment_matches"] is False


def test_wrong_canonical_name_rejected():
    envelope = _envelope("Eve")
    env = dict(envelope)
    material = dict(envelope["provenance_material"])
    material["canonical_name"] = "Nope"
    env["provenance_material"] = material
    result = pv.validate_provenance_source_envelope(_raw(env), _commitment(env))
    assert result["ok"] is False
    assert result["envelope_valid"] is False


def test_valid_envelope_confers_no_authority():
    envelope = _envelope("Adam")
    env = dict(envelope)
    material = dict(envelope["provenance_material"])
    material["operator_approval_ref"] = "any-caller-asserted-ref"
    env["provenance_material"] = material
    result = pv.validate_provenance_source_envelope(_raw(env), _commitment(env))
    # Structural validity does NOT imply authority/gate-open.
    assert result["ok"] is True
    assert result["commitment_matches"] is True


def test_preparsed_dict_is_not_accepted_as_equivalent():
    # A dict input (already materialized) cannot be a valid raw-JSON boundary:
    # only str/bytes carry duplicate-key evidence. Fail closed, never accepted.
    result = pv.validate_provenance_source_envelope(_envelope("Adam"), "0" * 64)
    assert result["ok"] is False
    assert result["envelope_valid"] is False
    assert result["commitment_matches"] is False