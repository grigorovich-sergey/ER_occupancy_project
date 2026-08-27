"""Load/export a configured standardized ED subset."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from er_occupancy.data_access import run_configured_access
from er_occupancy.foundations import resolve_config


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--default-config", default="configs/data_access_default.yaml"
    )
    parser.add_argument("--override-config")
    args = parser.parse_args(argv)
    config = resolve_config(args.default_config, args.override_config)
    loaded = run_configured_access(config)
    print(json.dumps(loaded.manifest_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
