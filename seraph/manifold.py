"""Ontology-neutral manifold compiler for functional transition invariants.

The compiler separates semantic description from functional consequence:

* a :class:`ManifoldSpec` declares the coordinates and invariant relations;
* a :class:`TransitionProposal` declares concrete coordinate changes;
* a :class:`CompiledManifold` evaluates the transition as proven, refuted, or
  unresolved; and
* an :class:`InvariantCertificate` binds that verdict to the exact manifold,
  source state, proposal, and expected target state.

Rules are data, not executable Python.  This keeps compilation deterministic,
content-addressed, and reproducible.  Unknown subjects, coordinates, evidence,
or state fail closed as ``unresolved``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any


Scalar = bool | int | float | str


class ManifoldVerdict(Enum):
    """Three-valued result for compiled invariant evaluation."""

    PROVEN = "proven"
    REFUTED = "refuted"
    UNRESOLVED = "unresolved"


class InvariantRelation(Enum):
    """Relations supported by the deterministic invariant IR."""

    PRESERVE = "preserve"
    NONDECREASING = "nondecreasing"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    EQUALS = "equals"


class ManifoldCompileError(ValueError):
    """Raised when a manifold constitution is structurally invalid."""

    def __init__(self, errors: tuple[str, ...]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_scalar(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return isfinite(value)
    return isinstance(value, str)


def _numeric(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


def _canonical(value: Any) -> Any:
    """Convert supported values to a stable JSON representation."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _canonical(asdict(value))
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical mappings require string keys")
        return {
            key: _canonical(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if _valid_scalar(value) or value is None:
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def content_digest(value: Any) -> str:
    """Return a deterministic SHA-256 digest for compiler data."""

    encoded = canonical_json(value).encode("utf-8")
    return sha256(encoded).hexdigest()


def canonical_json(value: Any) -> str:
    """Return the canonical JSON representation used by proof digests."""

    return json.dumps(
        _canonical(value),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True)
class Coordinate:
    """One named functional coordinate on an entity."""

    name: str
    value: Scalar

    def valid(self) -> bool:
        return _valid_identifier(self.name) and _valid_scalar(self.value)


@dataclass(frozen=True)
class EntityState:
    """An entity positioned on the manifold."""

    entity_id: str
    roles: tuple[str, ...]
    coordinates: tuple[Coordinate, ...]

    def valid(self) -> bool:
        names = [coordinate.name for coordinate in self.coordinates]
        return (
            _valid_identifier(self.entity_id)
            and bool(self.roles)
            and all(_valid_identifier(role) for role in self.roles)
            and len(set(self.roles)) == len(self.roles)
            and all(coordinate.valid() for coordinate in self.coordinates)
            and len(set(names)) == len(names)
        )

    def coordinate_map(self) -> dict[str, Scalar]:
        return {coordinate.name: coordinate.value for coordinate in self.coordinates}

    def with_coordinate(self, name: str, value: Scalar) -> EntityState:
        updated = self.coordinate_map()
        updated[name] = value
        return replace(
            self,
            coordinates=tuple(
                Coordinate(key, updated[key])
                for key in sorted(updated)
            ),
        )


@dataclass(frozen=True)
class ManifoldState:
    """A complete or explicitly partial observation of the manifold."""

    state_id: str
    entities: tuple[EntityState, ...]
    complete: bool = True

    def valid(self) -> bool:
        ids = [entity.entity_id for entity in self.entities]
        return (
            _valid_identifier(self.state_id)
            and isinstance(self.complete, bool)
            and all(entity.valid() for entity in self.entities)
            and len(set(ids)) == len(ids)
        )

    def entity_map(self) -> dict[str, EntityState]:
        return {entity.entity_id: entity for entity in self.entities}

    def functional_payload(self) -> dict[str, Any]:
        """Return state geometry without the human-facing observation label."""

        return {
            "entities": self.entities,
            "complete": self.complete,
        }


def functional_state_digest(state: ManifoldState) -> str:
    """Digest functional state while excluding its semantic/audit label."""

    return content_digest(state.functional_payload())


@dataclass(frozen=True)
class InvariantRule:
    """A coordinate relation evaluated over a role or explicit subject set."""

    rule_id: str
    coordinate: str
    relation: InvariantRelation
    subject_roles: tuple[str, ...] = ()
    subject_ids: tuple[str, ...] = ()
    threshold: Scalar | None = None

    def validation_errors(self, coordinate_names: set[str]) -> tuple[str, ...]:
        errors: list[str] = []
        if not _valid_identifier(self.rule_id):
            errors.append("invalid_rule_id")
        if self.coordinate not in coordinate_names:
            errors.append(f"unknown_rule_coordinate:{self.rule_id}")
        if not isinstance(self.relation, InvariantRelation):
            errors.append(f"invalid_rule_relation:{self.rule_id}")
        if not self.subject_roles and not self.subject_ids:
            errors.append(f"empty_rule_scope:{self.rule_id}")
        if (
            any(not _valid_identifier(role) for role in self.subject_roles)
            or len(set(self.subject_roles)) != len(self.subject_roles)
        ):
            errors.append(f"invalid_rule_roles:{self.rule_id}")
        if (
            any(not _valid_identifier(subject) for subject in self.subject_ids)
            or len(set(self.subject_ids)) != len(self.subject_ids)
        ):
            errors.append(f"invalid_rule_subjects:{self.rule_id}")

        needs_threshold = self.relation in {
            InvariantRelation.MINIMUM,
            InvariantRelation.MAXIMUM,
            InvariantRelation.EQUALS,
        }
        if needs_threshold and not _valid_scalar(self.threshold):
            errors.append(f"invalid_rule_threshold:{self.rule_id}")
        if not needs_threshold and self.threshold is not None:
            errors.append(f"unexpected_rule_threshold:{self.rule_id}")
        if (
            self.relation in {InvariantRelation.MINIMUM, InvariantRelation.MAXIMUM}
            and not _numeric(self.threshold)
        ):
            errors.append(f"nonnumeric_rule_threshold:{self.rule_id}")
        return tuple(errors)


@dataclass(frozen=True)
class EvidenceRequirement:
    """Evidence type and the external issuers trusted to attest it."""

    evidence_type: str
    trusted_issuers: tuple[str, ...]

    def valid(self) -> bool:
        return (
            _valid_identifier(self.evidence_type)
            and bool(self.trusted_issuers)
            and all(_valid_identifier(issuer) for issuer in self.trusted_issuers)
            and len(set(self.trusted_issuers)) == len(self.trusted_issuers)
        )


@dataclass(frozen=True)
class ConsequenceEdge:
    """A topology-owned directed path along which effects may propagate.

    Edges belong to :class:`ManifoldSpec`, never to a transition proposal.  The
    compiler treats them conservatively: an effect on ``source_id`` makes
    ``target_id`` reachable, and reachability continues to a fixed point.
    """

    source_id: str
    target_id: str

    def valid(self) -> bool:
        return (
            _valid_identifier(self.source_id)
            and _valid_identifier(self.target_id)
        )


@dataclass(frozen=True)
class ManifoldSpec:
    """Versioned constitutional rules for a mission manifold."""

    manifold_id: str
    version: str
    coordinate_names: tuple[str, ...]
    admitted_origins: tuple[str, ...]
    mutation_keys: tuple[str, ...]
    rules: tuple[InvariantRule, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    inhabitant_role: str = "inhabitant"
    require_complete_state: bool = True
    require_affected_inhabitants: bool = True
    require_reversibility: bool = False
    consequence_edges: tuple[ConsequenceEdge, ...] = ()

    def validation_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not _valid_identifier(self.manifold_id):
            errors.append("invalid_manifold_id")
        if not _valid_identifier(self.version):
            errors.append("invalid_manifold_version")
        if (
            not self.coordinate_names
            or any(not _valid_identifier(name) for name in self.coordinate_names)
            or len(set(self.coordinate_names)) != len(self.coordinate_names)
        ):
            errors.append("invalid_coordinate_names")
        if (
            not self.admitted_origins
            or any(not _valid_identifier(item) for item in self.admitted_origins)
            or len(set(self.admitted_origins)) != len(self.admitted_origins)
        ):
            errors.append("invalid_admitted_origins")
        if (
            not self.mutation_keys
            or any(not _valid_identifier(item) for item in self.mutation_keys)
            or len(set(self.mutation_keys)) != len(self.mutation_keys)
        ):
            errors.append("invalid_mutation_keys")
        if not _valid_identifier(self.inhabitant_role):
            errors.append("invalid_inhabitant_role")
        if not all(
            isinstance(value, bool)
            for value in (
                self.require_complete_state,
                self.require_affected_inhabitants,
                self.require_reversibility,
            )
        ):
            errors.append("invalid_manifold_flags")

        rule_ids = [rule.rule_id for rule in self.rules]
        if not self.rules or len(set(rule_ids)) != len(rule_ids):
            errors.append("invalid_rule_set")
        coordinates = set(self.coordinate_names)
        for rule in self.rules:
            errors.extend(rule.validation_errors(coordinates))

        edges_valid = all(
            isinstance(edge, ConsequenceEdge) and edge.valid()
            for edge in self.consequence_edges
        )
        edge_keys = (
            [
                (edge.source_id, edge.target_id)
                for edge in self.consequence_edges
            ]
            if edges_valid
            else []
        )
        if not edges_valid or len(set(edge_keys)) != len(edge_keys):
            errors.append("invalid_consequence_edges")

        evidence_types = [
            requirement.evidence_type
            for requirement in self.evidence_requirements
        ]
        if (
            len(set(evidence_types)) != len(evidence_types)
            or not all(
                requirement.valid()
                for requirement in self.evidence_requirements
            )
        ):
            errors.append("invalid_evidence_requirements")
        return tuple(errors)


@dataclass(frozen=True)
class FunctionalEffect:
    """A concrete coordinate change, independent of semantic action labels."""

    subject_id: str
    coordinate: str
    before: Scalar
    after: Scalar
    reversible: bool

    def valid(self) -> bool:
        return (
            _valid_identifier(self.subject_id)
            and _valid_identifier(self.coordinate)
            and _valid_scalar(self.before)
            and _valid_scalar(self.after)
            and isinstance(self.reversible, bool)
        )


@dataclass(frozen=True)
class EvidenceRecord:
    """Content-addressed evidence bound to the observed source state."""

    evidence_type: str
    issuer: str
    digest: str
    source_state_digest: str

    def valid(self) -> bool:
        return all(
            _valid_identifier(value)
            for value in (
                self.evidence_type,
                self.issuer,
                self.digest,
                self.source_state_digest,
            )
        )


@dataclass(frozen=True)
class TransitionProposal:
    """A proposed movement through a compiled mission manifold.

    ``label`` is retained for human auditability but deliberately excluded from
    the functional proposal digest and all invariant evaluation.
    """

    proposal_id: str
    manifold_id: str
    manifold_version: str
    source_state_digest: str
    actor_id: str
    origin_id: str
    effects: tuple[FunctionalEffect, ...]
    affected_inhabitants: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...] = ()
    execution_binding: str = ""
    label: str = ""

    def valid(self) -> bool:
        effect_keys = [
            (effect.subject_id, effect.coordinate)
            for effect in self.effects
        ]
        evidence_types = [record.evidence_type for record in self.evidence]
        return (
            all(
                _valid_identifier(value)
                for value in (
                    self.proposal_id,
                    self.manifold_id,
                    self.manifold_version,
                    self.source_state_digest,
                    self.actor_id,
                    self.origin_id,
                )
            )
            and isinstance(self.execution_binding, str)
            and isinstance(self.label, str)
            and all(effect.valid() for effect in self.effects)
            and len(set(effect_keys)) == len(effect_keys)
            and all(
                _valid_identifier(inhabitant)
                for inhabitant in self.affected_inhabitants
            )
            and len(set(self.affected_inhabitants))
            == len(self.affected_inhabitants)
            and all(record.valid() for record in self.evidence)
            and len(set(evidence_types)) == len(evidence_types)
        )

    def functional_payload(self) -> dict[str, Any]:
        """Return a canonical functional identity, excluding the semantic label.

        Effects and affected inhabitants are validated as unique collections;
        their presentation order is not part of the proposed transition.
        """

        return {
            "proposal_id": self.proposal_id,
            "manifold_id": self.manifold_id,
            "manifold_version": self.manifold_version,
            "source_state_digest": self.source_state_digest,
            "actor_id": self.actor_id,
            "origin_id": self.origin_id,
            "effects": self.canonical_effects(),
            "affected_inhabitants": tuple(sorted(self.affected_inhabitants)),
            "evidence": self.evidence,
            "execution_binding": self.execution_binding,
        }

    def canonical_effects(self) -> tuple[FunctionalEffect, ...]:
        """Return effects in their unique functional-key order."""

        return tuple(
            sorted(
                self.effects,
                key=lambda effect: (effect.subject_id, effect.coordinate),
            )
        )


@dataclass(frozen=True)
class InvariantResult:
    rule_id: str
    verdict: ManifoldVerdict
    reason: str
    subjects: tuple[str, ...] = ()


@dataclass(frozen=True)
class AffectedSetClosure:
    """Deterministic consequence reachability for one proposed transition."""

    seed_entities: tuple[str, ...]
    reached_entities: tuple[str, ...]
    affected_inhabitants: tuple[str, ...]
    unresolved_entities: tuple[str, ...]
    topology_digest: str

    @property
    def complete(self) -> bool:
        return not self.unresolved_entities


@dataclass(frozen=True)
class InvariantCertificate:
    """Deterministic proof artifact for one exact proposed transition."""

    # These digests bind the proof to the exact constitution,
    # source observation, functional proposal, and expected target.
    verdict: ManifoldVerdict
    manifold_digest: str
    source_state_digest: str
    proposal_digest: str
    target_state_digest: str | None
    affected_set: AffectedSetClosure
    results: tuple[InvariantResult, ...]
    reasons: tuple[str, ...]

    @property
    def proven(self) -> bool:
        return self.verdict is ManifoldVerdict.PROVEN


@dataclass(frozen=True)
class RealizationReport:
    """Comparison between the certified target and the realized state."""

    verdict: ManifoldVerdict
    expected_state_digest: str | None
    realized_state_digest: str
    reasons: tuple[str, ...]

    @property
    def matches(self) -> bool:
        return self.verdict is ManifoldVerdict.PROVEN


def _aggregate(results: tuple[InvariantResult, ...]) -> ManifoldVerdict:
    verdicts = {result.verdict for result in results}
    if ManifoldVerdict.REFUTED in verdicts:
        return ManifoldVerdict.REFUTED
    if ManifoldVerdict.UNRESOLVED in verdicts:
        return ManifoldVerdict.UNRESOLVED
    return ManifoldVerdict.PROVEN


def _compare(
    relation: InvariantRelation,
    before: Scalar,
    after: Scalar,
    threshold: Scalar | None,
) -> tuple[ManifoldVerdict, str]:
    if relation is InvariantRelation.PRESERVE:
        passes = after == before
    elif relation is InvariantRelation.NONDECREASING:
        if not _numeric(before) or not _numeric(after):
            return ManifoldVerdict.UNRESOLVED, "nonnumeric_coordinate"
        passes = after >= before
    elif relation is InvariantRelation.MINIMUM:
        if not _numeric(after) or not _numeric(threshold):
            return ManifoldVerdict.UNRESOLVED, "nonnumeric_coordinate"
        passes = after >= threshold
    elif relation is InvariantRelation.MAXIMUM:
        if not _numeric(after) or not _numeric(threshold):
            return ManifoldVerdict.UNRESOLVED, "nonnumeric_coordinate"
        passes = after <= threshold
    elif relation is InvariantRelation.EQUALS:
        passes = after == threshold
    else:
        return ManifoldVerdict.UNRESOLVED, "unknown_relation"
    return (
        (ManifoldVerdict.PROVEN, "invariant_preserved")
        if passes
        else (ManifoldVerdict.REFUTED, "invariant_violated")
    )


@dataclass(frozen=True)
class CompiledManifold:
    """Validated, content-addressed executable manifold constitution."""

    spec: ManifoldSpec
    digest: str

    def derive_affected_set(
        self,
        state: ManifoldState,
        proposal: TransitionProposal,
    ) -> AffectedSetClosure:
        """Close topology-owned consequence paths from declared effect roots.

        The proposal identifies concrete effect roots but cannot supply or
        narrow the graph.  Sorting every externally visible set makes the
        result stable across proposal ordering and graph cycles.
        """

        entity_map = state.entity_map()
        adjacency: dict[str, set[str]] = {}
        for edge in self.spec.consequence_edges:
            adjacency.setdefault(edge.source_id, set()).add(edge.target_id)

        seeds = tuple(sorted({effect.subject_id for effect in proposal.effects}))
        reached = set(seeds)
        frontier = list(seeds)
        while frontier:
            source_id = frontier.pop()
            for target_id in sorted(adjacency.get(source_id, ())):
                if target_id not in reached:
                    reached.add(target_id)
                    frontier.append(target_id)

        topology_entities = {
            endpoint
            for edge in self.spec.consequence_edges
            for endpoint in (edge.source_id, edge.target_id)
        }
        unresolved = (reached | topology_entities) - set(entity_map)
        affected = {
            entity_id
            for entity_id in reached
            if entity_id in entity_map
            and self.spec.inhabitant_role in entity_map[entity_id].roles
        }
        return AffectedSetClosure(
            seed_entities=seeds,
            reached_entities=tuple(sorted(reached)),
            affected_inhabitants=tuple(sorted(affected)),
            unresolved_entities=tuple(sorted(unresolved)),
            topology_digest=content_digest(self.spec.consequence_edges),
        )

    def evaluate(
        self,
        state: ManifoldState,
        proposal: TransitionProposal,
    ) -> InvariantCertificate:
        results: list[InvariantResult] = []
        canonical_effects = proposal.canonical_effects()

        def record(
            rule_id: str,
            verdict: ManifoldVerdict,
            reason: str,
            subjects: tuple[str, ...] = (),
        ) -> None:
            results.append(InvariantResult(rule_id, verdict, reason, subjects))

        if not state.valid():
            record(
                "compiler.state",
                ManifoldVerdict.UNRESOLVED,
                "invalid_source_state",
            )
        if self.spec.require_complete_state and not state.complete:
            record(
                "compiler.state_completeness",
                ManifoldVerdict.UNRESOLVED,
                "incomplete_source_state",
            )
        actual_source_digest = functional_state_digest(state)
        if proposal.source_state_digest != actual_source_digest:
            record(
                "compiler.source_binding",
                ManifoldVerdict.REFUTED,
                "source_state_digest_mismatch",
            )
        else:
            record(
                "compiler.source_binding",
                ManifoldVerdict.PROVEN,
                "source_state_bound",
            )

        if not proposal.valid():
            record(
                "compiler.proposal",
                ManifoldVerdict.UNRESOLVED,
                "invalid_transition_proposal",
            )
        if (
            proposal.manifold_id != self.spec.manifold_id
            or proposal.manifold_version != self.spec.version
        ):
            record(
                "compiler.manifold_binding",
                ManifoldVerdict.REFUTED,
                "manifold_version_mismatch",
            )
        else:
            record(
                "compiler.manifold_binding",
                ManifoldVerdict.PROVEN,
                "manifold_version_bound",
            )

        if proposal.origin_id not in self.spec.admitted_origins:
            record(
                "compiler.origin_binding",
                ManifoldVerdict.REFUTED,
                "unadmitted_transition_origin",
            )
        else:
            record(
                "compiler.origin_binding",
                ManifoldVerdict.PROVEN,
                "transition_origin_admitted",
            )

        entity_map = state.entity_map()
        coordinate_names = set(self.spec.coordinate_names)
        effects_structurally_valid = proposal.valid() and state.valid()
        for effect in canonical_effects:
            if effect.subject_id not in entity_map:
                record(
                    "compiler.effect_subject",
                    ManifoldVerdict.UNRESOLVED,
                    "unknown_effect_subject",
                    (effect.subject_id,),
                )
                effects_structurally_valid = False
                continue
            if effect.coordinate not in coordinate_names:
                record(
                    "compiler.effect_coordinate",
                    ManifoldVerdict.UNRESOLVED,
                    "unknown_effect_coordinate",
                    (effect.subject_id,),
                )
                effects_structurally_valid = False
                continue
            coordinates = entity_map[effect.subject_id].coordinate_map()
            if effect.coordinate not in coordinates:
                record(
                    "compiler.effect_coordinate",
                    ManifoldVerdict.UNRESOLVED,
                    "unobserved_effect_coordinate",
                    (effect.subject_id,),
                )
                effects_structurally_valid = False
                continue
            if coordinates[effect.coordinate] != effect.before:
                record(
                    "compiler.effect_binding",
                    ManifoldVerdict.REFUTED,
                    "effect_before_mismatch",
                    (effect.subject_id,),
                )
                effects_structurally_valid = False
                continue
            record(
                f"compiler.effect:{effect.subject_id}:{effect.coordinate}",
                ManifoldVerdict.PROVEN,
                "effect_bound_to_source",
                (effect.subject_id,),
            )

        if self.spec.require_reversibility:
            irreversible = tuple(
                effect.subject_id
                for effect in canonical_effects
                if not effect.reversible
            )
            record(
                "compiler.reversibility",
                (
                    ManifoldVerdict.REFUTED
                    if irreversible
                    else ManifoldVerdict.PROVEN
                ),
                (
                    "irreversible_transition"
                    if irreversible
                    else "transition_reversible"
                ),
                irreversible,
            )

        affected_set = self.derive_affected_set(state, proposal)
        if not affected_set.complete:
            record(
                "compiler.consequence_topology",
                ManifoldVerdict.UNRESOLVED,
                "topology_entity_unobserved",
                affected_set.unresolved_entities,
            )

        derived_inhabitants = set(affected_set.affected_inhabitants)
        declared_inhabitants = set(proposal.affected_inhabitants)
        invalid_declared = {
            inhabitant
            for inhabitant in declared_inhabitants
            if inhabitant not in entity_map
            or self.spec.inhabitant_role not in entity_map[inhabitant].roles
        }
        if self.spec.require_affected_inhabitants:
            if invalid_declared:
                record(
                    "compiler.inhabitant_scope",
                    ManifoldVerdict.UNRESOLVED,
                    "unknown_affected_inhabitant",
                    tuple(sorted(invalid_declared)),
                )
            omitted = derived_inhabitants - declared_inhabitants
            record(
                "compiler.inhabitant_coverage",
                (
                    ManifoldVerdict.REFUTED
                    if omitted
                    else ManifoldVerdict.PROVEN
                ),
                (
                    "affected_inhabitant_omitted"
                    if omitted
                    else "affected_set_complete"
                ),
                tuple(sorted(omitted or derived_inhabitants)),
            )
            unexpected = declared_inhabitants - derived_inhabitants
            record(
                "compiler.inhabitant_precision",
                (
                    ManifoldVerdict.REFUTED
                    if unexpected
                    else ManifoldVerdict.PROVEN
                ),
                (
                    "affected_inhabitant_not_derived"
                    if unexpected
                    else "affected_set_exact"
                ),
                tuple(sorted(unexpected or derived_inhabitants)),
            )
            effect_subjects = {effect.subject_id for effect in proposal.effects}
            unmodeled = derived_inhabitants - effect_subjects
            record(
                "compiler.inhabitant_effect_coverage",
                (
                    ManifoldVerdict.REFUTED
                    if unmodeled
                    else ManifoldVerdict.PROVEN
                ),
                (
                    "affected_inhabitant_effect_omitted"
                    if unmodeled
                    else "affected_inhabitant_effects_explicit"
                ),
                tuple(sorted(unmodeled or derived_inhabitants)),
            )

        evidence_map = {
            evidence.evidence_type: evidence
            for evidence in proposal.evidence
        }
        for requirement in self.spec.evidence_requirements:
            evidence = evidence_map.get(requirement.evidence_type)
            rule_id = f"compiler.evidence:{requirement.evidence_type}"
            if evidence is None:
                record(
                    rule_id,
                    ManifoldVerdict.UNRESOLVED,
                    "required_evidence_missing",
                )
            elif evidence.issuer not in requirement.trusted_issuers:
                record(
                    rule_id,
                    ManifoldVerdict.UNRESOLVED,
                    "untrusted_evidence_issuer",
                )
            elif evidence.source_state_digest != actual_source_digest:
                record(
                    rule_id,
                    ManifoldVerdict.UNRESOLVED,
                    "stale_evidence",
                )
            else:
                record(
                    rule_id,
                    ManifoldVerdict.PROVEN,
                    "evidence_bound",
                )

        target_state: ManifoldState | None = None
        if effects_structurally_valid:
            target_entities = entity_map.copy()
            for effect in canonical_effects:
                target_entities[effect.subject_id] = target_entities[
                    effect.subject_id
                ].with_coordinate(effect.coordinate, effect.after)
            target_state = ManifoldState(
                state_id=f"{state.state_id}->{proposal.proposal_id}",
                entities=tuple(
                    target_entities[key]
                    for key in sorted(target_entities)
                ),
                complete=state.complete,
            )
            before_entities = entity_map
            after_entities = target_state.entity_map()
            for rule in self.spec.rules:
                subjects = tuple(
                    entity_id
                    for entity_id, entity in sorted(before_entities.items())
                    if (
                        (not rule.subject_ids or entity_id in rule.subject_ids)
                        and (
                            not rule.subject_roles
                            or any(role in entity.roles for role in rule.subject_roles)
                        )
                    )
                )
                if not subjects:
                    record(
                        rule.rule_id,
                        ManifoldVerdict.UNRESOLVED,
                        "rule_scope_unobserved",
                    )
                    continue

                subject_verdicts: list[ManifoldVerdict] = []
                subject_reasons: list[str] = []
                for subject_id in subjects:
                    before = before_entities[subject_id].coordinate_map()
                    after = after_entities[subject_id].coordinate_map()
                    if (
                        rule.coordinate not in before
                        or rule.coordinate not in after
                    ):
                        subject_verdicts.append(ManifoldVerdict.UNRESOLVED)
                        subject_reasons.append("coordinate_unobserved")
                        continue
                    verdict, reason = _compare(
                        rule.relation,
                        before[rule.coordinate],
                        after[rule.coordinate],
                        rule.threshold,
                    )
                    subject_verdicts.append(verdict)
                    subject_reasons.append(reason)

                if ManifoldVerdict.REFUTED in subject_verdicts:
                    rule_verdict = ManifoldVerdict.REFUTED
                    rule_reason = "invariant_violated"
                elif ManifoldVerdict.UNRESOLVED in subject_verdicts:
                    rule_verdict = ManifoldVerdict.UNRESOLVED
                    rule_reason = "invariant_unresolved"
                else:
                    rule_verdict = ManifoldVerdict.PROVEN
                    rule_reason = "invariant_preserved"
                record(rule.rule_id, rule_verdict, rule_reason, subjects)

        result_tuple = tuple(results)
        verdict = _aggregate(result_tuple)
        reasons = tuple(
            dict.fromkeys(
                result.reason
                for result in result_tuple
                if result.verdict is not ManifoldVerdict.PROVEN
            )
        )
        return InvariantCertificate(
            verdict=verdict,
            manifold_digest=self.digest,
            source_state_digest=actual_source_digest,
            proposal_digest=content_digest(proposal.functional_payload()),
            target_state_digest=(
                functional_state_digest(target_state)
                if target_state is not None
                else None
            ),
            affected_set=affected_set,
            results=result_tuple,
            reasons=reasons,
        )

    def verify_certificate(
        self,
        certificate: InvariantCertificate,
        state: ManifoldState,
        proposal: TransitionProposal,
    ) -> bool:
        """Verify proof freshness by deterministic recompilation."""

        return (
            certificate.proven
            and certificate == self.evaluate(state, proposal)
        )

    def verify_realization(
        self,
        certificate: InvariantCertificate,
        realized_state: ManifoldState,
    ) -> RealizationReport:
        """Detect divergence between certified and realized consequences."""

        # Realized functional state must equal the target state bound into
        # the proof.
        realized_digest = functional_state_digest(realized_state)
        if not certificate.proven or certificate.manifold_digest != self.digest:
            return RealizationReport(
                verdict=ManifoldVerdict.UNRESOLVED,
                expected_state_digest=certificate.target_state_digest,
                realized_state_digest=realized_digest,
                reasons=("certificate_not_applicable",),
            )
        if certificate.target_state_digest != realized_digest:
            return RealizationReport(
                verdict=ManifoldVerdict.REFUTED,
                expected_state_digest=certificate.target_state_digest,
                realized_state_digest=realized_digest,
                reasons=("realized_state_diverged",),
            )
        return RealizationReport(
            verdict=ManifoldVerdict.PROVEN,
            expected_state_digest=certificate.target_state_digest,
            realized_state_digest=realized_digest,
            reasons=(),
        )


class ManifoldCompiler:
    """Validate and compile versioned manifold specifications."""

    @staticmethod
    def compile(
        spec: ManifoldSpec,
        *,
        previous: CompiledManifold | None = None,
        mutation_key: str | None = None,
    ) -> CompiledManifold:
        if all(
            isinstance(edge, ConsequenceEdge)
            for edge in spec.consequence_edges
        ):
            spec = replace(
                spec,
                consequence_edges=tuple(
                    sorted(
                        spec.consequence_edges,
                        key=lambda edge: (edge.source_id, edge.target_id),
                    )
                ),
            )
        errors = spec.validation_errors()
        if errors:
            raise ManifoldCompileError(errors)

        digest = content_digest(spec)
        if previous is not None:
            # Changed constitutional rules require a new version and an
            # admitted mutation key from the previous immutable constitution.
            if spec.manifold_id != previous.spec.manifold_id:
                raise ManifoldCompileError(("manifold_identity_changed",))
            if digest != previous.digest:
                mutation_errors: list[str] = []
                if spec.version == previous.spec.version:
                    mutation_errors.append("manifold_version_not_advanced")
                if mutation_key not in previous.spec.mutation_keys:
                    mutation_errors.append("unadmitted_manifold_mutation")
                if mutation_errors:
                    raise ManifoldCompileError(tuple(mutation_errors))
        return CompiledManifold(spec=spec, digest=digest)
