# SERAPH provenance

Prepared 2026-10-14. This document records SERAPH's architectural authorship, development checkpoints, and verifiable artifact identities. It does not amend earlier commits or establish exclusive novelty. The machine-readable [evidence manifest](docs/provenance/evidence.json) records exact identifiers and hashes.

## Architectural authorship and development

Amber Anson / Ambercontinuum Research identifies herself as the designer of SERAPH's architecture and research direction. Implementation, formalization, documentation, and adversarial review were developed with AI assistance, including Claude and OpenAI Codex. Repository author fields identify recorded commit authors; they do not, alone, determine who conceived or implemented every element. See the [development process](docs/development-process.md) and [design lineage](docs/design_lineage.md).

The design lineage separately acknowledges established work in runtime assurance, authorization, capability security, proof-carrying authorization, and agent-tool mediation. Those foundations are not claimed as inventions of this project. Empirical validation and formal guarantees remain bounded by the [verification boundary](README.md#verification-boundary).

## Architectural replacement with MCC

Commit `811a90cccbe1d748078f119b3970d5650efa43cc` replaced the fixed authority-vector layer with **Manifold Constraint Closure (MCC)**. The replacement uses topology- and transition-bound required relations, scoped observations and evidence references, and `PROVEN`, `REFUTED`, and `UNRESOLVED` resolution. Closure requires every required relation to be proven. It removes scalar authority aggregation and preserves the distinction between refutation and missing evidence.

The historical Python and Lean checkpoints below record the earlier authority-vector implementation. The MCC checkpoints record the later relational constraint architecture.

## Historical object checkpoints

These identifiers were resolved from the retained historical SERAPH Git repository. Historical blobs are not included in this release, and are not represented as reachable from this publication's fresh Git root. Their identifiers alone do not guarantee public availability. The manifest additionally records exact-byte SHA-256 digests, sizes, commit payload hashes, dates, and signature-presence metadata.

| Evidence | Full commit ID | Git blob ID |
| --- | --- | --- |
| historical-python-model | `05907caa399b70a3f7561650e3890df6fe1eafc1` | `60476873202b4885678e1733e906bce5eafe328c` |
| historical-lean-model | `314fa74be5e630e33b40366c1c8442f66fb643c2` | `1b76155a2f1013a23c909e5f7df3581aa4d238a3` |
| mcc-replacement | `811a90cccbe1d748078f119b3970d5650efa43cc` | `590c8b69ba5dc3124cff5a211dacbe0bf04e01a0` |
| mcc-formal-model | `811a90cccbe1d748078f119b3970d5650efa43cc` | `0acbf7854a4f9790f1ca967b5251fe1d8c05c9ab` |

The MCC replacement commit has a **cryptographically valid OpenPGP signature**, verified using the public key retrieved from the Ambercontinuum GitHub account on 2026-10-14. Its fingerprint is `60478B57AF12FE4ABCCB5B8967AD45206315CD5B`. The [public key](docs/provenance/signing-key.asc) is included for reproducibility; its digest is in SHA256SUMS. Verification used an isolated keyring with undefined owner trust. This establishes a signature-to-key binding, not independent real-world identity, first publication, or authorship of every design element. Per-artifact signature results are recorded in the manifest. Historical objects can be checked in a checkout that actually contains them using `git cat-file commit COMMIT`, `git rev-parse COMMIT:PATH`, and `git show COMMIT:PATH`. Hash exact exported bytes rather than text copied through an editor or shell pipeline that may change encoding or line endings.

## Public research-stack checkpoints

The [research-stack map](docs/research-stack.md) explains the connections already named by the included repositories, covering implemented telemetry interfaces, documented precursors, and the measurement program. It identifies the evidence and current integration boundary for each connection.

This inventory includes only the five repositories whose inspected public documentation explicitly names SERAPH. Dates are recorded committer dates of the earliest inspected default-branch history entries, normalized to UTC by the GitHub API. A first commit can be a template or minimal README; its date does not date every concept or later implementation. Repository creation dates and author dates are recorded separately in the manifest. Current public visibility does not establish when a repository first became public.

| Repository / immutable commit link | Recorded UTC date | Full commit ID |
| --- | --- | --- |
| [AMLA](https://github.com/Ambercontinuum/AMLA/commit/977314b3c44bfd1481586c704743388d2a5b203c) | 2025-12-09 | `977314b3c44bfd1481586c704743388d2a5b203c` |
| [CHANDRA](https://github.com/Ambercontinuum/CHANDRA/commit/29e0c08385135474477ca8750d529fcb065104d5) | 2025-12-03 | `29e0c08385135474477ca8750d529fcb065104d5` |
| [PDOT](https://github.com/Ambercontinuum/PDOT/commit/2ff1ae873495d79d2632e202b58632a3a442448f) | 2026-05-16 | `2ff1ae873495d79d2632e202b58632a3a442448f` |
| [SERAPH-1.0](https://github.com/Ambercontinuum/SERAPH-1.0/commit/da6a2ed0865984d6c2f0dfa0feacbcd8d61067a0) | 2026-10-14 | `da6a2ed0865984d6c2f0dfa0feacbcd8d61067a0` |
| [STK-Flux](https://github.com/Ambercontinuum/STK-Flux/commit/a87efd9dfadafe49be44ec1013f22509d82f314e) | 2026-03-04 | `a87efd9dfadafe49be44ec1013f22509d82f314e` |

An important content-bearing checkpoint is PDOT's [May 16 lineage document](https://github.com/Ambercontinuum/PDOT/blob/2ff1ae873495d79d2632e202b58632a3a442448f/docs/csa_seraph_lineage.md), which already names SERAPH as a governance runtime using coupling telemetry. STK-Flux's [March 4 commit](https://github.com/Ambercontinuum/STK-Flux/commit/a87efd9dfadafe49be44ec1013f22509d82f314e) includes Python, Lean, coupling documentation, and provenance. These demonstrate recorded earlier artifacts and connections; they do not establish that every current SERAPH mechanism existed at those dates.

The public SERAPH-1.0 repository was created as a fresh publication history. Its initial publication commit is `da6a2ed0865984d6c2f0dfa0feacbcd8d61067a0`; that release boundary is distinct from the project's earlier development history. Commit names, repository names, and version labels do not independently establish production readiness.

## Cryptographic verification and limits

The [manifest](docs/provenance/evidence.json) is UTF-8 JSON with exact-byte SHA-256 values. Its digest is recorded in [SHA256SUMS](docs/provenance/SHA256SUMS); for this revision it is `2e4f10d00474a43efde7b30d7100af962b16898305cd61b9453f1e0c1c67ce7b`. From `docs/provenance`, verify with `sha256sum -c SHA256SUMS`, or compare `Get-FileHash -Algorithm SHA256 -LiteralPath evidence.json` with the recorded digest in PowerShell.

Git object IDs in this evidence set use SHA-1 with Git's object-type/length framing. The independent SHA-256 values hash raw blob contents or raw commit payloads, without Git framing. These are deliberately different identifiers. Working-tree newline conversion can change a file's SHA-256 without changing the committed blob; verification must use exact repository-object bytes.

Hashes establish byte identity relative to a supplied digest. They do not prove authorship, originality, permission, historical possession, first publication, or absence of earlier work. Recorded Git dates can be set by an author; this bundle is not an independent trusted timestamp or notarization. A manifest and checksum delivered together need an independently trusted reference to resist replacement of both. The bundle contains technical metadata and a public verification key; it contains no private correspondence or transcripts.

Corrections to this document should be new, reviewable commits. Historical records should remain intact, with contribution claims tied to the specific evidence that supports them.
