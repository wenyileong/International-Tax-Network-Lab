# International Tax Network Lab

Local-first academic workbench for international-taxation network research.

## Build 0.1 status
Includes a runnable Streamlit shell, synthetic data, shared graph utilities, run provenance, a Jupyter starter, tests, and method reconstruction registers.

**The three methods are not assumed to be equivalent and are not yet claimed to be reproduced:**
1. Optimal tax routing associated with van 't Riet and Lejour.
2. Conduit and sink analysis associated with Garcia-Bernardo and co-authors.
3. Scalable topological data analysis described in US Patent 10,417,262 B2.

The model modules fail explicitly until their primary-source specifications have been transcribed and validated. This avoids inventing formulas or passing generic algorithms off as reproductions.

## Setup
Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[app,notebook,test]"
pytest
streamlit run app.py
```

Open `notebooks/01_research_workbench.ipynb` in JupyterLab after installation.

## Synthetic data warning
Jurisdictions (`JUR_A` etc.), companies, rates, values and links are fictional and only test software behaviour. They are not tax advice, legal statements about real countries, or empirical findings.

## Lawful data access
Before importing real data, check the source's licence, terms of use, database rights, redistribution limits, privacy obligations and automated-access restrictions. Prefer official public sources and documented APIs. Do not bypass access controls. Record source, access date, terms, transformations and limitations.
