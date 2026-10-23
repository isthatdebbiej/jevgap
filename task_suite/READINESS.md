# Ready for operator commissioning — 23 October 2026

The task reconciliation and full scoring implementation are complete. The
selected experiment uses official ACT Harness, Qwen, native GaP and native CaP.
Astra is retained. See [OPERATOR_HANDOFF.md](OPERATOR_HANDOFF.md) and the frozen
`operator-packet-v3` for launch, reset, scoring and commissioning instructions.

## Validated

- 106 checkout regression tests passed (one Linux-only module skipped on Windows).
- 25 Linux ACT tests passed, including actual SDK scoring export and a check that
  incomplete commissioning blocks study launch before contacting the station.
- Both native policy loops passed two-turn fake-ACT diagnostics with the agreed
  52-request limit. Earlier real Qwen vision diagnostics passed with fake ACT;
  those are connectivity/model-format checks, not physical manipulation evidence.
- All 17 base task profiles load into real SDK Task_Spec objects at 450 seconds.
- Full progress and quality rubrics cover 13 tasks: ten physical proposal tasks
  plus three explicitly supplemental tasks. All four precision/memory variants
  have separate measured-evidence scoring and observer protocols.
- Six language assignments produce 22 matched pairs / 44 individual episodes;
  policy order alternates. Task/plan hashes prevent accidental protocol drift.
- Tailscale relay TCP reachability and saved login-file presence were checked.
  This does not establish that the station is currently free or authenticated.

## Budget

The approved open-model ceiling is $230 in the existing shared reservation
ledger. Both policies allow 52 requests per episode. At $0.10 reserved per
request, the whole plan reserves at most $228.80 in addition to $0.50 already
reserved: $229.30 total. Additional commissioning calls use the same budget.
Provider billing is distinct from these client reservations. No Astra settings
or credentials were removed or printed.

## Operator session

The software is ready to bring the operator in for commissioning. Physical
start pose, reachable workspace, camera readability, measurement resolution,
video capture and fixture behavior must be observed at the station. The packet
contains the exact checklist and blank evidence records. Commissioning runs
are labelled and excluded from study results. Scored study runs require the
completed commissioning record; no record has been fabricated.

No physical evaluation was launched and no operator was contacted during this
work. Raw SE3 answers and separate progress/quality exports are retained. The
station's generic aggregate is deliberately not used as either study metric.
Older packet v1/v2 and READINESS-pre-ACT.md are superseded for this experiment.
