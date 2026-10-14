"""Capability-scoped delegation examples."""

from adapters.delegation import DelegationChain


def show(name: str, chain: DelegationChain, capability: str) -> None:
    decision, audit = chain.evaluate_action(
        action_name=name,
        required_capabilities={capability},
        request_commit=capability == "write",
    )
    print(f"\n{name}: {decision.decision.value}")
    print(f"active path: {decision.deployment_posture.active_path}")
    for line in audit:
        print(line)
    print("reasons:", ", ".join(decision.reasons))


def main() -> None:
    clean = (
        DelegationChain(
            origin_id="operator",
            origin_capabilities=frozenset({"plan", "search", "write"}),
        )
        .add(
            "orchestrator",
            granted_capabilities={"plan", "search", "write"},
            role="plan",
        )
        .add(
            "researcher",
            granted_capabilities={"search", "write"},
            role="search",
        )
        .add("writer", granted_capabilities={"write"}, role="write")
    )
    show("commit_report", clean, "write")

    expanded = (
        DelegationChain(
            origin_id="operator",
            origin_capabilities=frozenset({"plan", "write"}),
        )
        .add(
            "orchestrator",
            granted_capabilities={"plan", "write"},
            role="plan",
        )
        .add("worker", granted_capabilities={"write"}, role="act")
        .add(
            "scope-expander",
            granted_capabilities={"write", "admin"},
            role="act",
        )
    )
    show("write_config", expanded, "write")


if __name__ == "__main__":
    main()
