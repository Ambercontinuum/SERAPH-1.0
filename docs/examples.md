# Examples

Run a decision:

```powershell
python -m seraph --pretty
```

Run the scenario corpus:

```powershell
python -m seraph_demo
```

Regenerate the static website proof surface from real SERAPH evaluations:

```powershell
python -m seraph_demo.web_export
```

Then serve `docs/demo/` as static files. The checked-in JavaScript fixture is
deterministic and verified by the test suite against the exporter.

All governance examples declare a scoped constraint frame. The bundled JSON
fixtures in `seraph/examples/` use the CLI's declared-profile convenience path;
production callers
should submit independently evidenced observations.

## Included cases

- `release_gate_commit.json`: closed frame and healthy invariants commit
- `evidence_loss_denied.json`: guardian evidence degradation denies
- `prp_collapse_witness.json`: collapsing recovery routes to witness
- `environment_unsafe_denied.json`: lost containment denies
- `non_traversal_relocation_maneuver.json`: admissible relocation maneuvers
- `distillation_extraction_denied.json`: extraction coupling denies

The CLI output includes the final decision, active deployment path,
three-state constraint result, functional signature, all invariant reports, and
precedence-ordered reasons.
