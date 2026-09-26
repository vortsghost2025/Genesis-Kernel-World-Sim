"""Compat shim: the canonical mystery reveal module now lives in the backend
(backend/world/mystery_reveal.py) so the living runtime can import it as a
package member. This scratch-side path remains for existing tests and
tooling that load this file by path; it re-exports the canonical module.

Historical note: authored as a scratch-side pure design module during world
content work; promoted to the backend when the runtime integration spec
(docs/mystery_runtime_integration_spec.md) was implemented.
"""

from backend.world.mystery_reveal import (  # noqa: F401
    FORBIDDEN_PROJECTION_SUBSTRINGS,
    MYSTERY_LIBRARY,
    accrue_mystery_evidence,
    apply_reveal,
    check_reveal,
    get_myth_record,
    landmark_id_for,
    mystery_revealed,
    project_discoveries,
    project_unsettled_reports,
)
