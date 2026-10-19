import hashlib, json, platform
from datetime import datetime, timezone
from typing import Any
import pandas as pd
from taxnetlab import __version__

def dataframe_sha256(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False, lineterminator="\\n").encode("utf-8")).hexdigest()

def make_run_manifest(research_question: str, dataset_label: str, seed: int | None,
                      model_id: str, model_version: str, parameters: dict[str, Any],
                      data_tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    return {
        "manifest_schema_version":"1.0",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "research_question":research_question,
        "dataset":{"label":dataset_label,"synthetic":dataset_label=="synthetic","seed":seed,
                   "tables":{name:{"rows":int(len(df)),"columns":list(df.columns),
                                   "sha256_csv":dataframe_sha256(df)}
                             for name,df in sorted(data_tables.items())}},
        "model":{"id":model_id,"version":model_version},
        "parameters":parameters,
        "environment":{"python":platform.python_version(),"taxnetlab":__version__},
        "limitations":["A manifest records metadata; it does not establish model accuracy.",
                       "Synthetic data are illustrative, not empirical evidence."]
    }

def manifest_as_json(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True, default=str)
