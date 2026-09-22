# Station integration check

Mode: **simulation_dispatch**. Station measurements are in summary.json.
Executor: native. Provider: diagnostic.

- Workflow attempts: 4; failures: 0.
- Replaced pending observations: 31.
- Unresolved commands: 0.
- Execution outcomes: {'interrupted': 1, 'completed': 1}.
- Admission/observation rejections: {}.
- Workflow latency in ms: {'n': 4, 'p50': 129.0024505, 'p95': 152.496761}.

Acceptance is not completion. A shadow proposal is not an executed command.
Diagnostic workers make no model calls. This is an integration check, not a
performance comparison or evidence of physical hardware readiness. Ground-truth
and experimental RGB-D sources are configured separately. Task success is reported
from the station's independent measurements, not inferred from model decisions.
