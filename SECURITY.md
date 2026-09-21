# Security and credential handling

API keys stay in files outside this checkout. Pass their paths using
`ASTRA_KEY_FILE` and `JEV_KEY_FILE`. Providers only send credentials to their
configured official HTTPS endpoints, disable redirects and suppress remote error
bodies. No keys are needed for local tests.

The adapters use persistent SQLite budget ledgers shared by worker processes.
Defaults are $100 for Astra and $5 for Jev; failed or uncertain requests retain
their reservations. These are local experiment guards, not account-wide billing
limits. Do not delete or split ledgers to reset a pilot's spending.

Report suspected vulnerabilities through the hosting platform's private security
advisory feature when enabled. Never post credentials or sensitive recordings in
a public issue. Rotate any credential that has been exposed.

This repository is experimental simulation software. It does not implement a
hardware action bridge, certified safety controller or emergency-stop system.
See [the hardware guide](docs/hardware.md) before planning physical testing.
