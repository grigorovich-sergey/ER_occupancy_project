"""Run the foundations smoke check with repository example configs."""

from pathlib import Path

from er_occupancy.foundations.smoke import run_foundations_smoke


if __name__ == "__main__":
    import json

    repository_root = Path(__file__).resolve().parents[1]
    result = run_foundations_smoke(
        repository_root / "configs" / "foundations_smoke_default.yaml",
        repository_root / "configs" / "foundations_smoke_override.yaml",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
