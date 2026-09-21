"""Scan Git candidates; print filenames/rule names, never matching secrets."""

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "provider credential": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "personal Windows path": re.compile(rb"(?:[A-Za-z]:[\\/]+Users[\\/]|/mnt/[a-z]/Users/)"),
    "personal Linux home": re.compile(rb"/home/[A-Za-z0-9_.-]+/"),
}


def scan():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    problems = []
    count = 0
    for name in set(result.stdout.decode().split("\0")) - {""}:
        f = ROOT / name
        if not f.is_file() or f.suffix in {".mp4", ".png", ".jpg", ".zip", ".woff"}:
            continue
        count += 1
        data = f.read_bytes()
        for rule, pattern in RULES.items():
            if pattern.search(data):
                problems.append((name, rule))
        if f.name in {"astra.txt", "jev.txt"} or f.suffix in {".key", ".pem", ".sqlite"}:
            problems.append((name, "private file type"))
    for name, rule in problems:
        print(f"{name}: {rule}")
    print(f"Scanned {count} Git candidate text files; {len(problems)} findings.")
    return bool(problems)


if __name__ == "__main__":
    sys.exit(scan())
