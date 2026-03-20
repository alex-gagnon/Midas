"""Institution importers package.

Provides a unified `run_import()` entry point that dispatches to the
correct importer class based on the source name.

Supported sources:
  chase       — Chase checking/credit CSV
  capital_one — Capital One credit card CSV
  fidelity    — Fidelity transactions or positions CSV (auto-detected)
  vanguard    — Vanguard transactions or positions CSV (auto-detected)
  pdf         — PDF bank statement (requires pdfplumber)
"""

from .capital_one import CapitalOneImporter
from .chase import ChaseImporter
from .fidelity import FidelityImporter
from .pdf_extractor import extract_transactions as _pdf_extract
from .vanguard import VanguardImporter

__all__ = ["run_import"]

_IMPORTERS = {
    "chase": ChaseImporter,
    "capital_one": CapitalOneImporter,
    "fidelity": FidelityImporter,
    "vanguard": VanguardImporter,
}


def run_import(
    source: str,
    input_path: str,
    account_id: str,
    output_dir: str,
    mode: str = "append",
    import_type: str | None = None,
) -> int:
    """Dispatch to the appropriate importer and return rows written.

    Args:
        source:      Institution key: 'chase', 'capital_one', 'fidelity',
                     'vanguard', or 'pdf'.
        input_path:  Path to the source file (CSV or PDF).
        account_id:  Identifier to tag each output row (e.g. 'chk_001').
        output_dir:  Directory where output CSV files will be written.
        mode:        'append' (default) or 'overwrite'.
        import_type: For fidelity/vanguard — 'transactions' or 'holdings'.
                     If None, the importer auto-detects from the file headers.

    Returns:
        Number of rows written.

    Raises:
        ValueError: If *source* is not a recognised institution key.
    """
    source = source.lower().strip()

    if source == "pdf":
        return _pdf_extract(input_path, account_id, output_dir, mode)

    if source not in _IMPORTERS:
        raise ValueError(
            f"Unknown import source {source!r}. "
            f"Valid options: {sorted(_IMPORTERS.keys()) + ['pdf']}"
        )

    importer = _IMPORTERS[source]()

    # Dispatch based on the requested import type
    if import_type == "holdings":
        return importer.import_holdings(input_path, account_id, output_dir, mode)
    if import_type == "transactions":
        return importer.import_transactions(input_path, account_id, output_dir, mode)

    # import_type is None — let the importer auto-detect from file headers.
    # import_auto() defaults to import_transactions for importers that only
    # support one type (chase, capital_one), and auto-detects for multi-mode
    # importers (fidelity, vanguard).
    return importer.import_auto(input_path, account_id, output_dir, mode)
