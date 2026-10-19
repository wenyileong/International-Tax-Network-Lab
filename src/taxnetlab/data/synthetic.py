import pandas as pd

def make_synthetic_dataset(seed: int = 17) -> dict[str, pd.DataFrame]:
    # Fixed toy fixture; seed is recorded for future generated datasets, not used yet.
    jurisdictions = pd.DataFrame([
        {"jurisdiction_id":"JUR_A","display_name":"Illustrative Jurisdiction A","fictional":True,"gdp_usd_mn":500000},
        {"jurisdiction_id":"JUR_B","display_name":"Illustrative Jurisdiction B","fictional":True,"gdp_usd_mn":180000},
        {"jurisdiction_id":"JUR_C","display_name":"Illustrative Jurisdiction C","fictional":True,"gdp_usd_mn":90000},
        {"jurisdiction_id":"JUR_D","display_name":"Illustrative Jurisdiction D","fictional":True,"gdp_usd_mn":250000},
        {"jurisdiction_id":"JUR_E","display_name":"Illustrative Jurisdiction E","fictional":True,"gdp_usd_mn":120000},
    ])
    companies = pd.DataFrame([
        {"company_id":"CO_001","company_name":"Example Parent A","jurisdiction_id":"JUR_A","entity_type":"parent"},
        {"company_id":"CO_002","company_name":"Example Holdings B","jurisdiction_id":"JUR_B","entity_type":"holding"},
        {"company_id":"CO_003","company_name":"Example Finance C","jurisdiction_id":"JUR_C","entity_type":"finance"},
        {"company_id":"CO_004","company_name":"Example Operating D","jurisdiction_id":"JUR_D","entity_type":"operating"},
        {"company_id":"CO_005","company_name":"Example Subsidiary E","jurisdiction_id":"JUR_E","entity_type":"subsidiary"},
        {"company_id":"CO_006","company_name":"Example Local Op A","jurisdiction_id":"JUR_A","entity_type":"operating"},
        {"company_id":"CO_007","company_name":"Example Intermediate D","jurisdiction_id":"JUR_D","entity_type":"holding"},
    ])
    ownership = pd.DataFrame([
        {"shareholder_id":"CO_001","investee_id":"CO_002","ownership_pct":80.0,"capital_value_usd_mn":120.0,"observation_date":"2025-12-31","source_id":"SYNTHETIC_001"},
        {"shareholder_id":"CO_002","investee_id":"CO_003","ownership_pct":70.0,"capital_value_usd_mn":85.0,"observation_date":"2025-12-31","source_id":"SYNTHETIC_001"},
        {"shareholder_id":"CO_003","investee_id":"CO_004","ownership_pct":60.0,"capital_value_usd_mn":55.0,"observation_date":"2025-12-31","source_id":"SYNTHETIC_001"},
        {"shareholder_id":"CO_001","investee_id":"CO_007","ownership_pct":25.0,"capital_value_usd_mn":40.0,"observation_date":"2025-12-31","source_id":"SYNTHETIC_001"},
        {"shareholder_id":"CO_007","investee_id":"CO_005","ownership_pct":51.0,"capital_value_usd_mn":32.0,"observation_date":"2025-12-31","source_id":"SYNTHETIC_001"},
        {"shareholder_id":"CO_001","investee_id":"CO_006","ownership_pct":100.0,"capital_value_usd_mn":65.0,"observation_date":"2025-12-31","source_id":"SYNTHETIC_001"},
    ])
    tax_edges = pd.DataFrame([
        {"source_jurisdiction":"JUR_A","target_jurisdiction":"JUR_B","illustrative_effective_rate":0.08,"income_type":"dividend","rule_status":"synthetic_assumption","source_id":"SYNTHETIC_001"},
        {"source_jurisdiction":"JUR_B","target_jurisdiction":"JUR_C","illustrative_effective_rate":0.04,"income_type":"dividend","rule_status":"synthetic_assumption","source_id":"SYNTHETIC_001"},
        {"source_jurisdiction":"JUR_C","target_jurisdiction":"JUR_D","illustrative_effective_rate":0.12,"income_type":"dividend","rule_status":"synthetic_assumption","source_id":"SYNTHETIC_001"},
        {"source_jurisdiction":"JUR_A","target_jurisdiction":"JUR_D","illustrative_effective_rate":0.18,"income_type":"dividend","rule_status":"synthetic_assumption","source_id":"SYNTHETIC_001"},
        {"source_jurisdiction":"JUR_D","target_jurisdiction":"JUR_E","illustrative_effective_rate":0.06,"income_type":"dividend","rule_status":"synthetic_assumption","source_id":"SYNTHETIC_001"},
        {"source_jurisdiction":"JUR_B","target_jurisdiction":"JUR_E","illustrative_effective_rate":0.10,"income_type":"dividend","rule_status":"synthetic_assumption","source_id":"SYNTHETIC_001"},
    ])
    return {"jurisdictions":jurisdictions,"companies":companies,"ownership":ownership,"tax_edges":tax_edges}
