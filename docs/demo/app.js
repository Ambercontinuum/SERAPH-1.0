(() => {
  "use strict";

  const data = window.SERAPH_DEMO_DATA;
  if (!data || !Array.isArray(data.scenarios)) {
    document.body.textContent = "SERAPH demo evidence is missing.";
    return;
  }

  const byId = (id) => document.getElementById(id);
  const text = (id, value) => { byId(id).textContent = value; };
  const list = (values) => values.length ? values.join(", ") : "none";
  const shortHash = (value) => `${value.slice(0, 12)}…${value.slice(-8)}`;
  const nav = byId("scenario-nav");

  text("fixture-notice", data.fixture_notice);

  const renderTopology = (scenario) => {
    const graph = byId("topology-graph");
    graph.replaceChildren();
    if (!scenario.topology.edges.length) {
      const empty = document.createElement("span");
      empty.className = "node";
      empty.textContent = "no consequence edges";
      graph.append(empty);
      return;
    }
    scenario.topology.edges.forEach((edge, index) => {
      if (index === 0) {
        const source = document.createElement("span");
        source.className = "node";
        source.textContent = edge.source_id;
        graph.append(source);
      }
      const arrow = document.createElement("span");
      arrow.className = "arrow";
      arrow.textContent = "→";
      const target = document.createElement("span");
      target.className = "node";
      target.textContent = edge.target_id;
      graph.append(arrow, target);
    });
  };

  const renderEffects = (scenario) => {
    const container = byId("effects");
    container.replaceChildren();
    scenario.effects.forEach((effect) => {
      const row = document.createElement("div");
      row.className = "effect";
      row.textContent = `${effect.subject_id}.${effect.coordinate}: ${effect.before} → ${effect.after} · ${effect.reversible ? "reversible" : "irreversible"}`;
      container.append(row);
    });
  };

  const renderChecks = (scenario) => {
    const container = byId("checks");
    container.replaceChildren();
    const rank = { refuted: 0, unresolved: 1, proven: 2 };
    const ordered = [...scenario.checks].sort(
      (left, right) => rank[left.verdict] - rank[right.verdict],
    );
    ordered.forEach((check) => {
      const row = document.createElement("div");
      row.className = "check";
      const verdict = document.createElement("strong");
      verdict.className = check.verdict;
      verdict.textContent = check.verdict;
      const rule = document.createElement("code");
      rule.textContent = check.rule_id;
      const reason = document.createElement("span");
      reason.textContent = `${check.reason}${check.subjects.length ? ` / ${check.subjects.join(", ")}` : ""}`;
      row.append(verdict, rule, reason);
      container.append(row);
    });
  };

  const renderConsequence = (scenario) => {
    const card = byId("consequence-card");
    const container = byId("consequence");
    container.replaceChildren();
    if (!scenario.consequence) {
      card.classList.add("hidden");
      return;
    }
    card.classList.remove("hidden");
    [
      ["Checkpoint 1", scenario.consequence.first_checkpoint, false],
      ["Checkpoint 2", scenario.consequence.second_checkpoint, true],
      ["Containment", scenario.consequence.contained ? "activated" : "absent", true],
    ].forEach(([label, value, failure]) => {
      const box = document.createElement("div");
      box.className = `checkpoint${failure ? " failure" : ""}`;
      const caption = document.createElement("span");
      caption.textContent = label;
      const result = document.createElement("strong");
      result.textContent = value;
      box.append(caption, result);
      container.append(box);
    });
  };

  const render = (scenario, button) => {
    nav.querySelectorAll("button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    text("scenario-title", scenario.title);
    text("scenario-summary", scenario.summary);
    text("verdict", scenario.verdict.replaceAll("_", " "));
    byId("verdict").className = `verdict ${scenario.verdict}`;
    text("permit", scenario.permit_eligible ? "PERMIT ELIGIBLE" : "FAIL CLOSED");
    text("topology-digest", shortHash(scenario.topology.digest));
    text("proposal-digest", shortHash(scenario.proposal_digest));
    text("label", scenario.label);
    text(
      "label-binding",
      scenario.label_ignored_digest_match === true
        ? "No — opposite labels produce the same functional digest"
        : "Excluded from functional digest",
    );
    text("reached", list(scenario.reached_entities));
    text("derived", list(scenario.derived_affected));
    text("declared", list(scenario.declared_affected));
    text("unresolved", list(scenario.unresolved_entities));
    renderTopology(scenario);
    renderEffects(scenario);
    renderChecks(scenario);
    renderConsequence(scenario);
  };

  data.scenarios.forEach((scenario, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = scenario.title;
    button.addEventListener("click", () => render(scenario, button));
    nav.append(button);
    if (index === 0) render(scenario, button);
  });
})();
