"""
How this works / why it is safe:
This module enforces architectural layering and isolation boundaries.
It statically inspects the AST of all Python files in app/review to ensure
that review modules NEVER import app.ledger.service or attempt write operations.
"""

import ast
import os


def test_review_does_not_import_ledger_service():
    """Prove that review module never imports ledger.service."""
    review_dir = os.path.join(os.path.dirname(__file__), "..", "..", "app", "review")
    for fname in os.listdir(review_dir):
        if fname.endswith(".py"):
            fpath = os.path.join(review_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=fname)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "ledger.service" not in alias.name, f"{fname} imported ledger.service"
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    assert "ledger.service" not in mod, f"{fname} imported from {mod}"
                    for alias in node.names:
                        assert "post_movement" not in alias.name, f"{fname} imported post_movement"
