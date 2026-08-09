"""A miniature estate that all six checks pass against.

WHY A SYNTHETIC ESTATE AND NOT THE REAL ONE

The real estate is drifted today, so it cannot be the baseline: a self-test
whose starting point is red proves nothing when a mutation keeps it red. And
the checks' subjects live in sixteen other repositories, which this repository
reads and must never write. There is nowhere to mutate except a copy.

So the baseline is here: one file per anchor each check reads, in the same
shapes the real repositories use, wired so that every comparison agrees.
`selftest.py` materialises this into real git repositories in a temporary
directory, proves all six checks pass, then breaks ONE thing at a time and
requires exactly the matching finding to fire.

WHAT THIS PROVES, AND WHAT IT DOES NOT

It proves each check can see a break, can pass a clean estate, and fails
loudly rather than quietly when a subject vanishes or an anchor stops
matching. Said plainly, because the distinction matters: it does NOT prove the
shapes below still resemble the real repositories. A real anchor that changes
shape is caught by the checks going red against the real estate, which is what
the nightly run is for, and never by this file.

The files are deliberately small. Every line here exists because some check
reads it; there is nothing decorative.
"""

from __future__ import annotations

# ---------------------------------------------------------------- schemas

EVENT_V01 = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://taipanbox.dev/schemas/agent-event.schema.json",
  "type": "object",
  "required": ["schema", "ts", "source", "type", "agent_id"],
  "properties": {
    "schema": { "const": "taipanbox.dev/agent-event/v0.1" },
    "ts": { "type": "string" },
    "source": { "type": "string" },
    "type": { "type": "string" },
    "agent_id": { "type": "string", "pattern": "^agent://" },
    "severity": { "type": "string" },
    "on_behalf_of": { "type": "array", "items": { "type": "string" } },
    "data": { "type": "object" }
  }
}
"""

EVENT_V02 = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://taipanbox.dev/schemas/agent-event.v0.2.schema.json",
  "type": "object",
  "required": ["schema", "ts", "source", "type", "agent_id"],
  "properties": {
    "schema": { "const": "taipanbox.dev/agent-event/v0.2" },
    "agent_id": { "type": "string", "pattern": "^agent://[a-z0-9.-]+/[a-z0-9._/-]+$", "maxLength": 255 },
    "prev_hash": { "type": "string", "pattern": "^sha256:[0-9a-f]{64}$" }
  }
}
"""

PASSPORT = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://taipanbox.dev/schemas/agent-passport.schema.json",
  "type": "object",
  "required": ["id", "owner"],
  "properties": {
    "id": { "type": "string", "pattern": "^agent://" },
    "owner": { "type": "string" },
    "filesystem": { "type": "array" },
    "models": { "type": "array" }
  }
}
"""

SPEC = """# The agent passport specification

## 6 The event envelope

### 6.1 Fields

`source` and `type` are open strings.

### 6.2 Initial event-type registry

| `source` | `type` values |
|---|---|
| `tokenfuse` | `budget_exhausted` . `run_killed` |
| `engram` | `memory_written` . `memory_forgotten` |
| `idryx` | RESERVED, not emitted today: `behavior_anomaly` |
| `qryx` | `crypto_finding` |
| `wardryx` | `policy_allow` . `policy_deny` |
| `verdryx` | `eval_run` |
| `mockryx` | `sim_run` |
| `console` | `console_command` |
| `heraldyx` | `alert_sent` |

A row here is a CLAIM that the source writes those types into this envelope
today.

### 6.3 What this buys
"""

# ------------------------------------------------------------ chain vectors

VEC1_CANON = '{"agent_id":"agent://acme.example/a","source":"wardryx","type":"policy_deny"}'
VEC1_HASH = "sha256:" + "1" * 64
VEC2_CANON = '{"agent_id":"agent://acme.example/a","note":"обмеження","source":"tokenfuse"}'
VEC2_HASH = "sha256:" + "2" * 64

CHAIN_VECTORS = (
    '{\n'
    '  "comment": "Cross-language pinned vectors.",\n'
    '  "vectors": [\n'
    '    { "event": {}, "canonical": %s, "hash": "%s" },\n'
    '    { "event": {}, "canonical": %s, "hash": "%s" }\n'
    '  ]\n'
    '}\n'
) % (
    __import__("json").dumps(VEC1_CANON),
    VEC1_HASH,
    __import__("json").dumps(VEC2_CANON),
    VEC2_HASH,
)

CHAIN_TEST_GO = """package event

// The cross-language pinned vectors (testdata/chain-vectors.json).
const (
\tvecC1 = `%s`
\tvecH1 = "%s"
\tvecC2 = `%s`
\tvecH2 = "%s"
)
""" % (VEC1_CANON, VEC1_HASH, VEC2_CANON, VEC2_HASH)

CHAIN_TEST_PY = '''"""Pinned vectors, retyped from agent-stack-go."""

_VEC_CANONICAL_1 = (
    %r
)
_VEC_HASH_1 = "%s"

_VEC_CANONICAL_2 = (
    %r
)
_VEC_HASH_2 = "%s"
''' % (VEC1_CANON, VEC1_HASH, VEC2_CANON, VEC2_HASH)


# ---------------------------------------------------------------- tokenfuse

BREAKER_RS = """//! The Breaker.

pub enum BreakerReason {
    BudgetExceeded,
    DlpBlocked,
}

impl BreakerReason {
    pub fn as_wire_str(self) -> &'static str {
        match self {
            BreakerReason::BudgetExceeded => "budget_exceeded",
            BreakerReason::DlpBlocked => "dlp_blocked",
        }
    }

    pub fn http_status(self) -> u16 {
        match self {
            BreakerReason::DlpBlocked => 403,
            BreakerReason::BudgetExceeded => 402,
        }
    }
}
"""

OUTCOMES_RS = """//! Per-outcome unit economics.

use crate::breaker::BreakerReason;

const BLOCKED_DECISIONS: [BreakerReason; 2] = [
    BreakerReason::BudgetExceeded,
    BreakerReason::DlpBlocked,
];

pub fn is_blocked_decision(decision: &str) -> bool {
    BLOCKED_DECISIONS.iter().any(|r| r.as_wire_str() == decision)
}
"""

PRICEBOOK_RS = """//! Default price book shipped with the gateway binary.

use tokenfuse_core::{ModelPrice, PriceBook};

pub fn default_price_book() -> PriceBook {
    PriceBook::new()
        .with("claude-haiku", ModelPrice::per_mtok_usd(0.80, 4.0, 0.08, 1.0))
        .with("gpt-4o", ModelPrice::per_mtok_usd(2.50, 10.00, 1.25, 2.50))
        .with_fallback(ModelPrice::per_mtok_usd(15.0, 75.0, 1.5, 18.75))
}
"""

SINK_RS = """//! The trace Parquet sink.

impl ParquetSink {
    fn schema() -> Arc<Schema> {
        Arc::new(Schema::new(vec![
            Field::new("run_id", DataType::Utf8, false),
            Field::new("decision", DataType::Utf8, false),
            Field::new("cost_microusd", DataType::Int64, false),
            Field::new("step", DataType::UInt32, false),
            Field::new("outcome", DataType::Utf8, false),
        ]))
    }

    pub fn read_schema() -> Arc<Schema> {
        Arc::new(Schema::new(vec![
            Field::new("run_id", DataType::Utf8, false),
            Field::new("decision", DataType::Utf8, false),
            Field::new("cost_microusd", DataType::Int64, false),
            Field::new("step", DataType::UInt32, false),
            Field::new("outcome", DataType::Utf8, true),
        ]))
    }
}
"""

AGENT_EVENT_RS = """//! The agent-event exporter.

pub enum EventType {
    BudgetExhausted,
    RunKilled,
}

impl EventType {
    pub fn as_wire_str(self) -> &'static str {
        match self {
            EventType::BudgetExhausted => "budget_exhausted",
            EventType::RunKilled => "run_killed",
        }
    }
}

impl Exporter {
    pub fn emit(&self, kind: EventType) -> EmitOutcome {
        EmitOutcome::Written
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn cross_language_chain_vectors_pin() {
        let cases = [
            (
                serde_json::json!({}),
                r#"%s"#,
                "%s",
            ),
            (
                serde_json::json!({}),
                r#"%s"#,
                "%s",
            ),
        ];
    }
}
""" % (VEC1_CANON, VEC1_HASH, VEC2_CANON, VEC2_HASH)

CONSTANTS_JSON = """{
  "schema": "taipanbox.dev/tokenfuse-constants/v1",
  "schema_version": 1,
  "source_repo": "TAIPANBOX/tokenfuse",
  "blocked_decisions": ["budget_exceeded", "dlp_blocked"],
  "breaker_reasons": [
    { "wire": "budget_exceeded", "http_status": 402, "blocked_decision": true },
    { "wire": "dlp_blocked", "http_status": 403, "blocked_decision": true }
  ],
  "price_book": {
    "units": "microusd_per_mtok",
    "fallback": {
      "input_per_mtok_microusd": 15000000,
      "output_per_mtok_microusd": 75000000,
      "cache_read_per_mtok_microusd": 1500000,
      "cache_write_per_mtok_microusd": 18750000
    },
    "models": [
      {
        "model": "claude-haiku",
        "input_per_mtok_microusd": 800000,
        "output_per_mtok_microusd": 4000000,
        "cache_read_per_mtok_microusd": 80000,
        "cache_write_per_mtok_microusd": 1000000
      },
      {
        "model": "gpt-4o",
        "input_per_mtok_microusd": 2500000,
        "output_per_mtok_microusd": 10000000,
        "cache_read_per_mtok_microusd": 1250000,
        "cache_write_per_mtok_microusd": 2500000
      }
    ]
  },
  "trace_parquet": {
    "read_schema": [
      { "name": "run_id", "type": "Utf8", "nullable": false },
      { "name": "decision", "type": "Utf8", "nullable": false },
      { "name": "cost_microusd", "type": "Int64", "nullable": false },
      { "name": "step", "type": "UInt32", "nullable": false },
      { "name": "outcome", "type": "Utf8", "nullable": true }
    ],
    "write_schema": []
  }
}
"""

# ------------------------------------------------------------------ verdryx

COSTPER_PY = '''"""Cost per outcome."""

_PARQUET_OUTCOME_COLUMN = "outcome"
_PARQUET_COST_COLUMN = "cost_microusd"
_PARQUET_RUN_ID_COLUMN = "run_id"
_PARQUET_STEP_COLUMN = "step"
_PARQUET_DECISION_COLUMN = "decision"

#: The Breaker block-decision wire strings, mirroring tokenfuse.
_BLOCKED_DECISIONS = frozenset(
    {
        "budget_exceeded",
        "dlp_blocked",
    }
)


def _is_blocked_decision(decision: str) -> bool:
    return decision in _BLOCKED_DECISIONS
'''

PRICING_PY = '''"""Token to USD pricing, mirroring TokenFuse's default price book."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok_usd: float
    output_per_mtok_usd: float
    cache_read_per_mtok_usd: float = 0.0
    cache_write_per_mtok_usd: float = 0.0


class PriceBook:
    def with_price(self, model, price):
        return self

    def with_fallback(self, price):
        return self

    @classmethod
    def default(cls):
        return (
            cls()
            .with_price("claude-haiku", ModelPrice(0.80, 4.0, 0.08, 1.0))
            .with_price("gpt-4o", ModelPrice(2.50, 10.00, 1.25, 2.50))
            .with_fallback(ModelPrice(15.0, 75.0, 1.5, 18.75))
        )
'''

PASSPORT_GO = """package passport

import "regexp"

const maxURIBytes = 255

var (
	agentURIPattern = regexp.MustCompile(`^agent://[a-z0-9.-]+/[a-z0-9._/-]+$`)
)
"""

VERDRYX_EVENTS_PY = '''"""The verdryx event log."""

import re

SCHEMA = "taipanbox.dev/agent-event/v0.2"
SOURCE = "verdryx"

AGENT_ID_PATTERN = re.compile(r"^agent://[a-z0-9.-]+/[a-z0-9._/-]+$")
AGENT_ID_MAX_LENGTH = 255

EVENT_SEVERITY: dict[str, str] = {
    "eval_run": "info",
}


class EventLog:
    def emit(self, event_type, agent_id, data):
        return None
'''

VERDRYX_CLI_PY = '''"""verdryx command line."""

from .events import EventLog


def run(log: EventLog, agent_id):
    log.emit("eval_run", agent_id, {})
'''

# ------------------------------------------------------------------- engram

ENGRAM_EVENTS_PY = '''"""The engram event log."""

import re

AGENT_ID_PATTERN = re.compile(r"^agent://[a-z0-9.-]+/[a-z0-9._/-]+$")
AGENT_ID_MAX_LENGTH = 255

SCHEMA = "taipanbox.dev/agent-event/v0.1"
SOURCE = "engram"

EVENT_SEVERITY: dict[str, str] = {
    "memory_written": "info",
    "memory_forgotten": "info",
}


class EventLog:
    def emit(self, event_type, agent_id, data):
        return None
'''

ENGRAM_CORE_PY = '''"""engram core."""


class Engram:
    def remember(self, episode_id):
        self._events.emit("memory_written", self._agent_id, {"memory_id": episode_id})

    def forget(self, episode_id):
        self._events.emit("memory_forgotten", self._agent_id, {"memory_id": episode_id})
'''

ENGRAM_REFLECTION_PY = '''"""engram reflection."""


def reflect(events, agent_id):
    return None
'''

# ---------------------------------------------------------------- Go planes

QRYX_EXPORTER_GO = """package exporter

import "github.com/TAIPANBOX/agent-stack-go/event"

const (
\tTypeCryptoFinding = "crypto_finding"
)

func New(path string) (*Exporter, error) {
\tw, err := event.NewChainedWriter(path)
\tif err != nil {
\t\treturn nil, err
\t}
\treturn &Exporter{w: w}, nil
}

func (e *Exporter) EmitFindings(f Finding) error {
\treturn e.w.Write(event.Event{
\t\tSource: "qryx",
\t\tType:   TypeCryptoFinding,
\t})
}
"""

WARDRYX_MAIN_GO = """package main

import "github.com/TAIPANBOX/agent-stack-go/event"

func main() {
\tew, err := event.NewChainedWriter(*eventsPath)
\t_ = ew
\t_ = err
}
"""

WARDRYX_API_GO = """package api

const (
\tevPolicyAllow = "policy_allow"
\tevPolicyDeny  = "policy_deny"
)

func (s *Server) decide() {
\ts.emit(evPolicyAllow, "info", "", "", nil, nil)
\ts.emit(evPolicyDeny, "high", "", "", nil, nil)
}
"""

MOCKRYX_EVENTS_GO = """package events

import "github.com/TAIPANBOX/agent-stack-go/event"

const Source = "mockryx"

func New(path string) (*Emitter, error) {
\tw, err := event.NewChainedWriter(path)
\treturn &Emitter{w: w}, err
}

func (e *Emitter) SimRun(runID string) error {
\treturn e.write(event.Event{
\t\tType: "sim_run",
\t})
}
"""

HERALDYX_RECORD_GO = """package record

import "github.com/TAIPANBOX/agent-stack-go/event"

const Source = "heraldyx"

const TypeAlertSent = "alert_sent"

func NewJournal(path string) (*Journal, error) {
\tw, err := event.NewChainedWriter(path)
\treturn &Journal{w: w}, err
}

func (j *Journal) Write() error {
\treturn j.w.Write(event.Event{
\t\tSource: Source,
\t\tType:   TypeAlertSent,
\t})
}
"""

IDRYX_INGEST_GO = """package tokenfuse

import "github.com/TAIPANBOX/agent-stack-go/event"

// idryx READS the envelope and never writes it: no NewWriter, no
// NewChainedWriter anywhere in this module.
func Load(path string) ([]event.Event, error) {
\treturn event.ReadFile(path)
}
"""

# ------------------------------------------------------------------ genaryx

GENARYX_COMMAND_RS = """//! The console command record.

pub fn build_line(rec: &Record) -> Value {
    let mut obj = Map::new();
    obj.insert("source".to_string(), Value::String("console".to_string()));
    obj.insert("type".to_string(), Value::String("console_command".to_string()));
    Value::Object(obj)
}
"""

# ------------------------------------------------------------------- taipan

TAIPAN_DEMO_RS = """//! `taipan demo`: append synthetic agent-event envelopes.

const SAMPLE_EVENTS: &[(&str, &str, &str)] = &[
    ("tokenfuse", "budget_exhausted", "critical"),
    ("wardryx", "policy_allow", "info"),
];

pub fn run(args: DemoArgs) -> Result<()> {
    Ok(())
}
"""

# -------------------------------------------------------------- deployments

STACK_UP_ROUTINES = """#!/usr/bin/env bash
# The five governance routines.

ROUTINE_NAMES=(focus-export qryx-trend verdryx-drift idryx-detect mockryx-drill)
DEFAULT_ROUTINES=(focus-export qryx-trend verdryx-drift idryx-detect)
"""

STACK_UP_UP = """#!/usr/bin/env bash
# stack-up: the local sandbox.

GATEWAY_PORT=4100
CLOUD_PORT=8080
DASH_PORT=3000
WARDRYX_PORT=8090
IDRYX_PORT=8081

start_gateway() {
  "$GATEWAY_BIN" &
  register gateway "$!" INT
}

start_cloud() {
  "$CLOUD_BIN" &
  register cloud "$!" TERM
}

start_dashboard() {
  python3 -m http.server "$DASH_PORT" --bind 127.0.0.1 &
  register dashboard "$!" TERM
}

start_wardryx() {
  "$WARDRYX_BIN" serve -addr "127.0.0.1:$WARDRYX_PORT" &
  register wardryx "$!" TERM
}

start_idryx() {
  "$IDRYX_BIN" serve --addr "127.0.0.1:$IDRYX_PORT" &
  register idryx "$!" TERM
}

start_heraldyx() {
  HERALDYX_MIN_SEVERITY="medium" \\
    "$HERALDYX_BIN" --from-now=false &
  register heraldyx "$!" TERM
}
"""

STACK_SINGLE_COMPOSE = """name: agent-stack

services:
  init-volumes:
    image: busybox:1.36
    restart: "no"

  policy-db:
    image: postgres:16-alpine

  wardryx:
    image: stack/wardryx:dev
    command:
      - serve
      - -addr
      - 0.0.0.0:8090

  idryx:
    image: stack/idryx:dev
    command:
      - serve
      - --addr
      - 0.0.0.0:8081

  heraldyx:
    image: stack/heraldyx:dev
    environment:
      HERALDYX_MIN_SEVERITY: ${ALERT_MIN_SEVERITY:-high}

  tokenfuse-cloud:
    image: stack/tokenfuse:dev
    environment:
      PORT: "8080"

  tokenfuse-gateway:
    image: stack/tokenfuse:dev
    environment:
      TOKENFUSE_ADDR: 0.0.0.0:4100
    ports:
      - "${GATEWAY_BIND:-127.0.0.1}:4100:4100"

  wg:
    image: stack/wg:dev

  caddy:
    image: stack/caddy:dev

  console:
    image: stack/genaryx-console:dev
    ports:
      - "127.0.0.1:7420:7420"

volumes:
  events:
"""

STACK_SINGLE_INSTALL = """#!/usr/bin/env bash
# stack-single installer.

add_env_default() {
  local name="$1" value="$2"
  grep -q "^${name}=" .env 2>/dev/null && return 0
  printf '%s=%s\\n' "$name" "$value" >>.env
}

add_env_default ALERT_MIN_SEVERITY high
"""

K8S_PLANES = """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tokenfuse-gateway
  namespace: agent-stack
spec:
  template:
    spec:
      containers:
        - name: gateway
---
apiVersion: v1
kind: Service
metadata: { name: tokenfuse-gateway, namespace: agent-stack }
spec:
  ports: [{ name: http, port: 4100, targetPort: http }]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tokenfuse-cloud
  namespace: agent-stack
spec:
  template:
    spec:
      containers:
        - name: cloud
---
apiVersion: v1
kind: Service
metadata: { name: tokenfuse-cloud, namespace: agent-stack }
spec:
  ports: [{ name: http, port: 8080, targetPort: http }]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wardryx
  namespace: agent-stack
spec:
  template:
    spec:
      containers:
        - name: wardryx
---
apiVersion: v1
kind: Service
metadata: { name: wardryx, namespace: agent-stack }
spec:
  ports: [{ name: http, port: 8090, targetPort: http }]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: idryx
  namespace: agent-stack
spec:
  template:
    spec:
      containers:
        - name: idryx
---
apiVersion: v1
kind: Service
metadata: { name: idryx, namespace: agent-stack }
spec:
  ports: [{ name: http, port: 8081, targetPort: http }]
"""

K8S_CONSOLE = """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: genaryx-console
  namespace: agent-stack
spec:
  template:
    spec:
      containers:
        - name: console
---
apiVersion: v1
kind: Service
metadata: { name: genaryx-console, namespace: agent-stack }
spec:
  ports: [{ name: http, port: 7420, targetPort: http }]
"""

K8S_STORE = """---
apiVersion: v1
kind: Service
metadata:
  name: policy-db
  namespace: agent-stack
spec:
  ports: [{ name: postgres, port: 5432, targetPort: postgres }]
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: policy-db
  namespace: agent-stack
spec:
  template:
    spec:
      containers:
        - name: postgres
"""

K8S_ROUTINES = """---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: crypto-trend
  namespace: agent-stack
spec:
  schedule: "17 3 * * *"
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: identity-sweep
  namespace: agent-stack
spec:
  schedule: "42 4 * * *"
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: quality-drift
  namespace: agent-stack
spec:
  schedule: "57 3 * * *"
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: drills
  namespace: agent-stack
spec:
  schedule: "0 5 * * 1"
  suspend: true
"""

K8S_HERALDYX = """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: heraldyx
  namespace: agent-stack
spec:
  template:
    spec:
      containers:
        - name: heraldyx
          env:
            # The floor below which nothing is mailed.
            - { name: HERALDYX_MIN_SEVERITY, value: "high" }
"""

K8S_KUSTOMIZATION = """apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: agent-stack
resources:
  - 10-planes.yaml
  - 15-policy-store.yaml
  - 20-console.yaml
  - 40-routines.yaml
"""


def gomod(module: str, pin: str | None = None) -> str:
    text = f"module github.com/TAIPANBOX/{module}\n\ngo 1.26\n"
    if pin:
        text += f"\nrequire github.com/TAIPANBOX/agent-stack-go {pin}\n"
    return text


# The whole fixture estate: repo -> {path: contents}. `_tags` is consumed by
# selftest.py when it materialises the git repositories.
ESTATE: dict[str, dict] = {
    "agent-passport": {
        "schemas/agent-event.schema.json": EVENT_V01,
        "schemas/agent-event.v0.2.schema.json": EVENT_V02,
        "schemas/agent-passport.schema.json": PASSPORT,
        "SPEC.md": SPEC,
    },
    "agent-stack-go": {
        "go.mod": gomod("agent-stack-go"),
        "passport/passport.go": PASSPORT_GO,
        "cmd/agent-conform/schemas/agent-event.schema.json": EVENT_V01,
        "cmd/agent-conform/schemas/agent-event.v0.2.schema.json": EVENT_V02,
        "cmd/agent-conform/schemas/agent-passport.schema.json": PASSPORT,
        "event/testdata/agent-event.v0.2.schema.json": EVENT_V02,
        "event/testdata/chain-vectors.json": CHAIN_VECTORS,
        "event/chain_test.go": CHAIN_TEST_GO,
        "_tags": ["v0.1.0", "v0.5.1"],
    },
    "tokenfuse": {
        "crates/core/src/breaker.rs": BREAKER_RS,
        "crates/core/src/outcomes.rs": OUTCOMES_RS,
        "crates/core/src/agent_event.rs": AGENT_EVENT_RS,
        "crates/gateway/src/pricebook.rs": PRICEBOOK_RS,
        "crates/gateway/src/sink.rs": SINK_RS,
        "contracts/tokenfuse-constants.json": CONSTANTS_JSON,
    },
    "verdryx": {
        "verdryx/costper.py": COSTPER_PY,
        "verdryx/pricing.py": PRICING_PY,
        "verdryx/events.py": VERDRYX_EVENTS_PY,
        "verdryx/cli.py": VERDRYX_CLI_PY,
        "tests/fixtures/agent-event.v0.2.schema.json": EVENT_V02,
        "tests/test_events.py": CHAIN_TEST_PY,
    },
    "engram": {
        "engram/events.py": ENGRAM_EVENTS_PY,
        "engram/core.py": ENGRAM_CORE_PY,
        "engram/reflection.py": ENGRAM_REFLECTION_PY,
        "tests/fixtures/agent-event.v0.2.schema.json": EVENT_V02,
        "tests/test_events.py": CHAIN_TEST_PY,
    },
    "genaryx": {
        "crates/core/src/schemas/agent-event.v0.1.schema.json": EVENT_V01,
        "crates/core/src/schemas/agent-event.v0.2.schema.json": EVENT_V02,
        "crates/core/src/command.rs": GENARYX_COMMAND_RS,
    },
    "idryx": {
        "go.mod": gomod("idryx", "v0.5.1"),
        "internal/ingest/tokenfuse/tokenfuse.go": IDRYX_INGEST_GO,
    },
    "qryx": {
        "go.mod": gomod("qryx", "v0.5.1"),
        "internal/exporter/exporter.go": QRYX_EXPORTER_GO,
    },
    "wardryx": {
        "go.mod": gomod("wardryx", "v0.5.1"),
        "cmd/wardryx/main.go": WARDRYX_MAIN_GO,
        "internal/api/api.go": WARDRYX_API_GO,
    },
    "mockryx": {
        "go.mod": gomod("mockryx", "v0.5.1"),
        "internal/events/events.go": MOCKRYX_EVENTS_GO,
    },
    "heraldyx": {
        "go.mod": gomod("heraldyx", "v0.5.1"),
        "internal/record/record.go": HERALDYX_RECORD_GO,
    },
    "terraform-provider-taipan": {"go.mod": gomod("terraform-provider-taipan", "v0.5.1")},
    "taipan": {"src/commands/demo.rs": TAIPAN_DEMO_RS},
    "stack-up": {"routines.sh": STACK_UP_ROUTINES, "up.sh": STACK_UP_UP},
    "stack-single": {
        "compose.yaml": STACK_SINGLE_COMPOSE,
        "install.sh": STACK_SINGLE_INSTALL,
    },
    "stack-k8s": {
        "manifests/10-planes.yaml": K8S_PLANES,
        "manifests/15-policy-store.yaml": K8S_STORE,
        "manifests/20-console.yaml": K8S_CONSOLE,
        "manifests/40-routines.yaml": K8S_ROUTINES,
        "manifests/45-heraldyx.yaml": K8S_HERALDYX,
        "manifests/kustomization.yaml": K8S_KUSTOMIZATION,
    },
    "trailryx": {"README.md": "# trailryx\n"},
    "catalog": {"README.md": "# catalog\n"},
    "bank-in-a-box": {"README.md": "# bank-in-a-box\n"},
}

# The expectations file the fixture's C5 run measures against. The fixture
# estate is built so that the divergences below are the only ones.
EXPECTATIONS = {
    "comment": ["The fixture's own expectations. See selftest/fixture.py."],
    "families": {
        "routines": {
            "what": "Governance routines each deployment installs.",
            "agreed": [
                "focus-export",
                "qryx-trend",
                "verdryx-drift",
                "idryx-detect",
                "mockryx-drill",
            ],
            "divergences": {
                "routines:stack-up:disabled:mockryx-drill": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "opt-in behind --with-drill",
                },
                "routines:stack-k8s:disabled:mockryx-drill": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "suspend: true",
                },
                "routines:stack-k8s:absent:focus-export": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "no CronJob for it",
                },
                "routines:stack-single:absent:focus-export": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "stack-single schedules nothing",
                },
                "routines:stack-single:absent:qryx-trend": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "stack-single schedules nothing",
                },
                "routines:stack-single:absent:verdryx-drift": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "stack-single schedules nothing",
                },
                "routines:stack-single:absent:idryx-detect": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "stack-single schedules nothing",
                },
                "routines:stack-single:absent:mockryx-drill": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "stack-single schedules nothing",
                },
            },
        },
        "min_severity": {
            "what": "The HERALDYX_MIN_SEVERITY default.",
            "agreed": "high",
            "divergences": {
                "min_severity:stack-up:medium": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "local sandbox, one operator",
                }
            },
        },
        "ports": {
            "what": "The fixed local port each component listens on.",
            "agreed": {
                "tokenfuse-gateway": 4100,
                "tokenfuse-cloud": 8080,
                "wardryx": 8090,
                "idryx": 8081,
                "console": 7420,
                "policy-db": 5432,
                "dashboard": 3000,
            },
            "divergences": {},
        },
        "services": {
            "what": "Which components each deployment brings up.",
            "agreed": [
                "tokenfuse-gateway",
                "tokenfuse-cloud",
                "wardryx",
                "idryx",
                "heraldyx",
                "console",
                "policy-db",
            ],
            "divergences": {
                "services:stack-up:absent:console": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "static dashboard instead",
                },
                "services:stack-up:extra:dashboard": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "static dashboard instead",
                },
                "services:stack-up:absent:policy-db": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "local disk store",
                },
                "services:stack-single:extra:wg": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "reachable from outside",
                },
                "services:stack-single:extra:caddy": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "TLS in front of the console",
                },
                "services:stack-single:extra:init-volumes": {
                    "recorded": "2026-08-06",
                    "provenance": "@claude",
                    "why": "one-shot volume layout",
                },
            },
        },
    },
}

REGISTRY = {
    "comment": ["The fixture estate. See selftest/fixture.py."],
    "repos": {
        name: {
            "github": None if name in ("taipan", "bank-in-a-box") else f"TAIPANBOX/{name}",
            "why_no_remote": "fixture: stands in for a repo with no public remote",
            "local": name,
            "role": "fixture",
        }
        for name in ESTATE
    },
}
