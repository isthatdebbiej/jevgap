# Offline execution check — identical local workers

Each row below summarizes whole episodes; percentiles within an episode are not independent trials.

| System | Attempts (episodes) | Pickup success | Median workflow (ms) | Median change → fresh dispatch (ms) | Stale proposals | RTF range |
|---|---:|---:|---:|---:|---:|---:|
| A | 1 | 0/1 | 574.1 | 1364.9 | 0 | 1.000–1.000 |
| B | 1 | 0/1 | 417.2 | 1355.0 | 1 | 1.000–1.000 |

No uncertainty claim is made from this small development sample. Missing responses and unsuccessful episodes remain in the JSON summaries.

The scene change is a scripted motion reversal. Camera mode estimates position from RGB-D but does not yet detect scene changes from images. These runs use a known red cube and experimental simulation finger contacts.

Native eligible-to-start timing uses output-ready timestamps from wrappers; native internal queue/dispatch timestamps are unavailable. Rust separately records dispatch, worker and result receipt. Neither number is pure scheduler overhead.

Decision-worker latency includes provider request construction, networking and parsing (or the diagnostic sleep). Normal GaP tracing remains enabled. WSL results are development measurements, not native-Linux publication measurements.
