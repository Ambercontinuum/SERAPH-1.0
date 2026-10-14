# Security and deployment boundary

SERAPH is a research artifact, not a production security boundary. Its HTTP
sidecar has no built-in authentication, uses in-memory session state, and has
no automatic retention bound. Bind it to loopback; do not expose it directly
to an untrusted network. In Docker, publish with `-p 127.0.0.1:8000:8000`.

The OpenClaw adapter trusts host hooks and declared tool profiles. It does not
confine unmediated code, inspect shell effects, establish sensor truth, or measure
symbolic pressure from tool names. Warn-only mode deliberately permits actions
that enforcing mode would block. A host can bypass governance if integration
or deployment authority permits it.

Report a suspected vulnerability privately to the maintainer contact in
COMMERCIAL.md before posting exploit details. Include affected version, expected
behavior, actual behavior, and a reproduction without secrets. No response-time
or remediation guarantee is made for this research alpha.
