"""Schema types for Phase 7 fog-of-war world mapping.

This module is intentionally dependency-light and import-only. It defines the
dictionary shapes used by the pure fog-of-war helpers without touching runtime
state, provider code, daemon loops, or canonical data files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NotRequired, TypedDict


SCHEMA_VERSION = "7B.1"


class Coordinates(TypedDict):
    x: int | float
    y: int | float


class ContinentDict(TypedDict):
    continent_id: str
    name: str


class RegionDict(TypedDict):
    region_id: str
    continent_id: str
    name: str


class TileDict(TypedDict):
    tile_id: str
    continent_id: str
    region_id: str
    coordinates: Coordinates
    terrain: str
    biome: str
    elevation: int | float
    water: dict[str, Any] | None
    resources: list[str]
    hazards: list[str]
    landmark_ids: list[str]
    blocks_travel: bool


class LandmarkDict(TypedDict):
    landmark_id: str
    continent_id: str
    tile_id: str
    kind: str
    hidden_name: NotRequired[str]
    description: NotRequired[str]


class ResourceDict(TypedDict, total=False):
    resource_id: str
    tile_id: str
    kind: str
    renewable: bool


class HazardDict(TypedDict, total=False):
    hazard_id: str
    tile_id: str
    kind: str
    severity: int | float


class MysteryDict(TypedDict, total=False):
    mystery_id: str
    tile_id: str
    kind: str
    reveal_threshold: int


class TravelEdgeDict(TypedDict):
    from_tile_id: str
    to_tile_id: str
    mode: str
    locked_by: NotRequired[str]


class TrueMapDict(TypedDict):
    schema_version: str
    world_id: str
    seed: str
    continents: list[ContinentDict]
    regions: list[RegionDict]
    tiles: list[TileDict]
    landmarks: list[LandmarkDict]
    resources: list[ResourceDict]
    hazards: list[HazardDict]
    mysteries: list[MysteryDict]
    travel_edges: list[TravelEdgeDict]


class KnownTileDict(TypedDict):
    tile_id: str
    first_observed_tick: int
    last_observed_tick: int
    visit_count: int
    confidence: float
    observed_terrain: str
    observed_biome: str
    observed_resources: list[str]
    observed_hazards: list[str]
    agent_given_name: str | None
    notes: list[str]


class KnownLandmarkDict(TypedDict):
    true_landmark_id: str
    first_observed_tick: int
    last_observed_tick: int
    kind: str
    confidence: float
    description: str


class NamedPlaceDict(TypedDict):
    true_landmark_id: str
    agent_given_name: str
    first_named_tick: int
    name_reason: str
    previous_names: list[str]


class RouteDict(TypedDict, total=False):
    route_id: str
    tile_ids: list[str]
    agent_given_name: str
    confidence: float


class HypothesisDict(TypedDict):
    id: str
    created_tick: int
    claim: str
    basis: str
    confidence: float
    status: str


class ContactEvidenceDict(TypedDict, total=False):
    evidence_id: str
    agent_id: str
    tick: int
    type: str
    tile_id: str
    confidence: float
    interpretation: str
    reveals_agent: bool
    level: int


class KnownMapDict(TypedDict):
    schema_version: str
    agent_id: str
    known_tiles: dict[str, KnownTileDict]
    known_landmarks: dict[str, KnownLandmarkDict]
    named_places: dict[str, NamedPlaceDict]
    routes: list[RouteDict]
    hypotheses: list[HypothesisDict]
    myths: list[dict[str, Any]]
    contact_evidence: list[ContactEvidenceDict]
    last_observation_tick: int


class WorldPositionDict(TypedDict):
    schema_version: str
    agent_id: str
    active: bool
    continent_id: str | None
    region_id: str | None
    tile_id: str | None
    coordinates: Coordinates | None
    facing: str | None
    movement_mode: str
    travel_capabilities: list[str]
    last_moved_tick: int | None


class ObservationResultDict(TypedDict):
    schema_version: str
    agent_id: str
    position: dict[str, Any]
    visible_tile_ids: list[str]
    visible_tiles: list[dict[str, Any]]
    visible_landmarks: list[dict[str, Any]]
    available_actions: list[str]
    hypotheses: list[HypothesisDict]


@dataclass(frozen=True)
class Continent:
    continent_id: str
    name: str


@dataclass(frozen=True)
class Region:
    region_id: str
    continent_id: str
    name: str


@dataclass(frozen=True)
class Tile:
    tile_id: str
    continent_id: str
    region_id: str
    coordinates: Coordinates
    terrain: str
    biome: str
    elevation: int | float = 0.0
    water: dict[str, Any] | None = None
    resources: list[str] = field(default_factory=list)
    hazards: list[str] = field(default_factory=list)
    landmark_ids: list[str] = field(default_factory=list)
    blocks_travel: bool = False


@dataclass(frozen=True)
class Landmark:
    landmark_id: str
    continent_id: str
    tile_id: str
    kind: str
    hidden_name: str = ""
    description: str = ""


@dataclass(frozen=True)
class Resource:
    resource_id: str
    tile_id: str
    kind: str
    renewable: bool = True


@dataclass(frozen=True)
class Hazard:
    hazard_id: str
    tile_id: str
    kind: str
    severity: int | float = 0.0


@dataclass(frozen=True)
class Mystery:
    mystery_id: str
    tile_id: str
    kind: str
    reveal_threshold: int = 1


@dataclass(frozen=True)
class TravelEdge:
    from_tile_id: str
    to_tile_id: str
    mode: str
    locked_by: str = ""


@dataclass(frozen=True)
class KnownTile:
    tile_id: str
    first_observed_tick: int
    last_observed_tick: int
    visit_count: int
    confidence: float
    observed_terrain: str
    observed_biome: str
    observed_resources: list[str] = field(default_factory=list)
    observed_hazards: list[str] = field(default_factory=list)
    agent_given_name: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnownLandmark:
    true_landmark_id: str
    first_observed_tick: int
    last_observed_tick: int
    kind: str
    confidence: float
    description: str = ""


@dataclass(frozen=True)
class NamedPlace:
    true_landmark_id: str
    agent_given_name: str
    first_named_tick: int
    name_reason: str
    previous_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Route:
    route_id: str
    tile_ids: list[str]
    agent_given_name: str = ""
    confidence: float = 1.0


@dataclass(frozen=True)
class Hypothesis:
    id: str
    created_tick: int
    claim: str
    basis: str
    confidence: float
    status: str = "unverified"


@dataclass(frozen=True)
class ContactEvidence:
    evidence_id: str
    type: str
    level: int
    reveals_agent: bool = False
    agent_id: str = ""
    tick: int = 0
    tile_id: str = ""
    confidence: float = 0.0
    interpretation: str = ""


@dataclass(frozen=True)
class WorldPosition:
    agent_id: str
    active: bool
    continent_id: str | None
    region_id: str | None
    tile_id: str | None
    coordinates: Coordinates | None
    facing: str | None
    movement_mode: str
    travel_capabilities: list[str] = field(default_factory=list)
    last_moved_tick: int | None = None


@dataclass(frozen=True)
class ObservationResult:
    agent_id: str
    position: dict[str, Any]
    visible_tile_ids: list[str]
    visible_tiles: list[dict[str, Any]]
    visible_landmarks: list[dict[str, Any]]
    available_actions: list[str]
    hypotheses: list[HypothesisDict] = field(default_factory=list)
