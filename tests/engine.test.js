import test from "node:test";
import assert from "node:assert/strict";
import {
  analyzeDocument,
  classifyModality,
  comparePolicy,
  compareVersions,
  evidenceGraph,
} from "../dist/js/engine.js";

const gdpr = "In the case of a personal data breach, the controller shall without undue delay and, where feasible, not later than 72 hours after having become aware of it, notify the personal data breach to the supervisory authority, unless the breach is unlikely to result in a risk to the rights and freedoms of natural persons.";

test("classifies normative modality and epistemic may-not separately", () => {
  assert.equal(classifyModality("The provider must retain logs.").label, "OBLIGATION");
  assert.equal(classifyModality("The provider must not disclose secrets.").label, "PROHIBITION");
  assert.equal(classifyModality("Records may not be complete.").label, "INFORMATION");
});

test("extracts an evidence-linked deadline and exception", () => {
  const analysis = analyzeDocument(gdpr, { sourceId: "eur-lex://gdpr/33", section: "Article 33" });
  const record = analysis.normative[0];
  assert.equal(record.modality, "OBLIGATION");
  assert.match(record.actor, /controller/i);
  assert.match(record.action, /^notify the personal data breach/i);
  assert.equal(record.condition, "feasible");
  assert.match(record.deadline, /72 hours/i);
  assert.match(record.exception, /unlikely/i);
  assert.equal(record.sourceId, "eur-lex://gdpr/33");
  assert.equal(Array.from(gdpr).slice(record.sourceSpan.start, record.sourceSpan.end).join(""), record.evidence);
  assert.equal(analysis.summary.citationIntegrity, 1);
});

test("locates repeated clauses after Unicode text without reusing the first span", () => {
  const source = "🧭 Context heading.\nThe provider must retain logs.\nThe provider must retain logs.";
  const duties = analyzeDocument(source).normative;
  assert.equal(duties.length, 2);
  assert.ok(duties[0].sourceSpan.end < duties[1].sourceSpan.start);
  for (const duty of duties) {
    assert.equal(Array.from(source).slice(duty.sourceSpan.start, duty.sourceSpan.end).join(""), duty.evidence);
  }
});

test("flags a slower policy deadline as a mismatch", () => {
  const policy = "The controller shall notify the supervisory authority no later than 96 hours after confirming a reportable breach.";
  const result = comparePolicy(gdpr, policy);
  assert.equal(result.outcome, "POTENTIAL_MISMATCH");
  assert.ok(result.dimensions.find((d) => d.id === "timing").score < 1);
});

test("detects modified and added obligations across versions", () => {
  const before = "The organization shall review accounts every 90 days.";
  const after = "The organization shall review accounts every 60 days. Dormant accounts must be disabled immediately.";
  const result = compareVersions(before, after);
  assert.ok(result.changes.some((change) => change.type === "MODIFIED"));
  assert.ok(result.changes.some((change) => change.type === "ADDED"));
  assert.ok(result.criticalCount >= 1);
});

test("explains observable time changes and marks unknown motives", () => {
  const before = "The controller shall notify the authority within five days. The organization shall retain records for three years.";
  const after = "The controller shall notify the authority within 72 hours. The organization shall retain records for seven years. The controller must document delays.";
  const changes = compareVersions(before, after).changes;
  const notification = changes.find((change) => change.type === "MODIFIED" && change.after.includes("notify"));
  assert.match(notification.explanation.observed, /five days to 72 hours/);
  assert.equal(notification.explanation.status, "INFERRED_FROM_TEXT");
  assert.equal(notification.severity, "CRITICAL");
  const retention = changes.find((change) => change.type === "MODIFIED" && change.after.includes("retain"));
  assert.match(retention.explanation.observed, /retention period/);
  const addition = changes.find((change) => change.type === "ADDED");
  assert.equal(addition.explanation.status, "UNDETERMINED");
});

test("reads hyphenated retention period as twenty-four months", () => {
  const before = "The security owner shall retain review evidence for twelve months.";
  const after = "The security owner shall retain review evidence for twenty-four months.";
  const change = compareVersions(before, after).changes[0];
  assert.equal(change.explanation.observed, "The retention period changed from twelve months to twenty-four months (extended).");
  assert.match(change.explanation.possibleRationale, /preserve records for longer/);
});

test("builds a navigable evidence graph", () => {
  const record = analyzeDocument(gdpr).normative[0];
  const graph = evidenceGraph(record);
  assert.ok(graph.nodes.some((node) => node.id === "source"));
  assert.ok(graph.nodes.some((node) => node.id === "obligation"));
  assert.ok(graph.edges.some((edge) => edge.label === "asserts"));
});

