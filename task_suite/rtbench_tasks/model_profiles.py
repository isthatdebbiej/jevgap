"""Additional open-model experiment profiles; existing Astra settings are retained."""
import copy
from pathlib import Path

MODELS = ("Qwen/Qwen3.8-27B", "nvidia/Qwen3.8-Flash-Next-NVFP4", "nvidia/Kimi-K3-NVFP4")


def openmodel_config(*, key_file="REPLACE-with-private-openmodels-key-file", budget_ledger="costplusiq-budget.sqlite"):
    return {"provider": "costplusiq", "model_id": MODELS[0], "key_file": str(key_file),
            "budget_ledger": str(budget_ledger), "budget_usd": 0, "reservation_usd": 0,
            "max_input_bytes": 64000, "max_output_tokens": 2048, "timeout_s": 60,
            "reasoning_effort": "low"}


def add_openmodel_profiles(directory, original, *, prefix="se3"):
    from .experiment import write_json
    profile = copy.deepcopy(original)
    profile["name"] += "-openmodels"
    profile["model"] = openmodel_config()
    write_json(Path(directory) / f"{prefix}-openmodels.local.json", profile)
