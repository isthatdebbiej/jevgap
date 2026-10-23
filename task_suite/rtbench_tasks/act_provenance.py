"""Pin native ACT runners including the explicit CaP import-only adaptation."""
import hashlib
import json
import subprocess
from pathlib import Path


def verify(root, harness):
    root=Path(root).resolve()
    def git(*args):
        return subprocess.check_output(["git","-c","core.autocrlf=true","-c","core.filemode=false","-C",str(root),*args],text=True,timeout=60).strip()
    expected = "c8b5515df80d3029ca5dc7f7f1ec1c327b70bbea"
    allowed={}
    if harness == "cap":
        data=json.loads(Path(__file__).with_name("cap-act-adaptation.json").read_text())
        expected,allowed=data["upstream_revision"],data["files"]
    revision=git("rev-parse","HEAD")
    if revision != expected:
        raise ValueError("native checkout revision mismatch")
    changed=set(git("diff","HEAD","--name-only").splitlines())
    if changed-set(allowed):
        raise ValueError("unrecorded native source modifications")
    if git("ls-files","--others","--exclude-standard"):
        raise ValueError("untracked native files can alter imports")
    for file,digest in allowed.items():
        if hashlib.sha256((root/file).read_bytes()).hexdigest()!=digest:
            raise ValueError("CaP import adaptation does not match recorded hash")
    return {"revision":revision,"adaptation_sha256":allowed}
