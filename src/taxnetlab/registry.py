"""Jurisdiction registry: ISO 3166-1 alpha-3 codes bundled with the software (plan s 10.2, Phase 7).

Used to check identifiers of real jurisdictions and to name them in templates. Codes that are well formed
but not assigned (for example user-assigned codes such as XKX) produce a warning, not an error, because
some data sources use them.
"""

from __future__ import annotations

import functools
import json

from taxnetlab.buildinfo import resource_path


@functools.lru_cache(maxsize=1)
def iso3_names() -> dict[str, str]:
    return json.loads(resource_path("data", "iso3166.json").read_text(encoding="utf-8"))["codes"]


def is_assigned(code: str) -> bool:
    return code in iso3_names()
