# Security and credential handling

The study covers GaP, CaP-X, ASPIRE and ENPIRE. Keep credentials outside
the checkout and use each harness's documented private configuration. No keys
are needed for offline adapter tests. Upstream processes use their own credential
and budget mechanisms; the coordinator's native GaP controls do not govern their
requests. See [harness setup](task_suite/HARNESSES.md).

The Astra/Jev providers used by the executor experiments use `ASTRA_KEY_FILE` and `JEV_KEY_FILE`. Those
providers only send credentials to their configured official HTTPS endpoints,
disable redirects and suppress remote error bodies.

Those providers use persistent SQLite budget ledgers shared by worker processes.
Defaults are $100 for Astra and $5 for Jev; failed or uncertain requests retain
their reservations. These are local experiment guards, not account-wide billing
limits. Do not delete or split ledgers to reset a pilot's spending.

Report suspected vulnerabilities through the hosting platform's private security
advisory feature when enabled. Never post credentials or sensitive recordings in
a public issue. Rotate any credential that has been exposed.

This repository is experimental robot policy software. The task suite includes an
SE3 SDK bridge but does not implement a
calibrated hardware driver, certified safety controller or emergency-stop system.
See the [task-suite driver requirements](task_suite/DRIVER.md) and
[upstream environment contract](task_suite/HARNESSES.md#task-and-evaluator-export-contract)
before planning physical testing.

The native GaP task-suite provider uses a private key-file path in local configuration and
a separate, explicitly funded request-reservation ledger (default zero). It
uses the official Responses HTTPS endpoint with redirects disabled. SE3 uses
its saved SDK login and operator-provided Tailscale network. Local configuration
and raw results are ignored by Git. See [task setup](task_suite/SETUP.md) for
budget semantics and [driver requirements](task_suite/DRIVER.md) before live use.
