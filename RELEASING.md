# Releasing

Every release is built and self-tested by CI on a Windows runner. A release is published by pushing a version tag; tag pushes are made by the author (the build sessions cannot push tags).

## Checklist

1. **Version.** Set the same version in `src/taxnetlab/__init__.py`, `pyproject.toml` and `CITATION.cff` (PEP 440 form, for example `1.0.0rc1` or `1.0.0`), and add the release to `CHANGELOG.md`.
2. **Generated documents are current.** `python scripts/make_check_pack.py` and `python scripts/make_api_docs.py`; copy `src/taxnetlab/guide/user_guide.md` to `docs/USER_GUIDE.md`. Tests fail if any of them is stale.
3. **Approved outputs.** `tests/regression/approved.json` changes only with a documented, intended change of outputs (regenerate with `python -m regression.snapshots` from `tests`, with `src` on `PYTHONPATH`).
4. **Tests.** `python -m pytest` on Python 3.11 and 3.12; optional differential tests with `pip install -e ".[test,differential]"`.
5. **Browser check.** Every page in both reading modes and both themes, with no script errors.
6. **Push to `main`** and wait for CI: tests on Windows and Linux, the executable and the installer built, installed without administrator rights, self-tested, and uninstalled.
7. **Physical Windows smoke test** (plan s 11.1) on Windows 10 and Windows 11 with the CI artefacts; record the result in the release notes.
8. **Tag:** `git tag v1.0.0 && git push origin v1.0.0`. CI attaches the executable, the installer and `SHA256SUMS.txt` to a GitHub release.
9. **Archive:** connect the repository to Zenodo (metadata in `.zenodo.json`), set the licence and access right, and add the DOI to `CITATION.cff` and the README.

## Conditions for 1.0 (plan s 1.4) that only the author can satisfy

* at least two method engines at `verified` (complete the records in `docs/verification/records`), and one at `replicated` or `replicated_with_discrepancies` (freeze an expectation, then run on real data);
* the physical Windows 10 and 11 smoke test;
* the licence decision (`LICENSE`) and an archived release with a DOI;
* the IP decision for the patent-method engine (it may stay at `interface`; release 1.0 needs only two engines).

Code signing (plan s 11.2) is optional; until then each release publishes SHA-256 checksums. Signing removes the Windows SmartScreen warning and needs a code-signing certificate held by the author (an organisation-validated or individual certificate from a certificate authority, or Azure Trusted Signing); the build then signs `taxnetlab.exe` and the installer with `signtool` before the checksums are written.

Continuous integration runs on GitHub Actions. A private repository has a monthly allowance of minutes; when it is used up, runs stay queued and never start (as happened to 1.0.0rc2). Check the allowance under Settings, Billing and plans, before a release.
