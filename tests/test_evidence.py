import csv
from pathlib import Path

import pytest

from short_rate_anomaly_regimes.evidence import ArticleManifest, load_article_manifest


def test_article_manifest_validates_required_evidence_roles(tmp_path: Path) -> None:
    manifest_path = tmp_path / "article_manifest.yaml"
    manifest_path.write_text(
        """
title: Short-Term Interest Rates and Stock Market Anomalies
authors:
  - Paulo F. Maio
  - Pedro Santa-Clara
doi: 10.1017/S002210901700028X
journal: Journal of Financial and Quantitative Analysis
volume: "52"
issue: "3"
pages: 927-961
publication_date: 2017-06
files:
  - role: article_pdf
    title: Final article PDF
    local_path: references/private/article.pdf
    sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    access_note: Legal personal research copy.
  - role: supplement
    title: Publisher supplementary material
    local_path: references/private/supplement.pdf
    sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    access_note: Legal personal research copy.
""",
        encoding="utf-8",
    )

    manifest = load_article_manifest(manifest_path)

    assert manifest.file_roles == {"article_pdf", "supplement"}


def test_article_manifest_rejects_invalid_checksum() -> None:
    with pytest.raises(ValueError, match="String should match pattern"):
        ArticleManifest.model_validate(
            {
                "title": "Short-Term Interest Rates and Stock Market Anomalies",
                "authors": ["Paulo F. Maio", "Pedro Santa-Clara"],
                "doi": "10.1017/S002210901700028X",
                "journal": "Journal of Financial and Quantitative Analysis",
                "volume": "52",
                "issue": "3",
                "pages": "927-961",
                "publication_date": "2017-06",
                "files": [
                    {
                        "role": "article_pdf",
                        "title": "Final article PDF",
                        "local_path": "references/private/article.pdf",
                        "sha256": "not-a-sha",
                        "access_note": "Legal personal research copy.",
                    }
                ],
            }
        )


def test_article_manifest_requires_article_and_supplement() -> None:
    with pytest.raises(ValueError, match="Missing required evidence roles: supplement"):
        ArticleManifest.model_validate(
            {
                "title": "Short-Term Interest Rates and Stock Market Anomalies",
                "authors": ["Paulo F. Maio", "Pedro Santa-Clara"],
                "doi": "10.1017/S002210901700028X",
                "journal": "Journal of Financial and Quantitative Analysis",
                "volume": "52",
                "issue": "3",
                "pages": "927-961",
                "publication_date": "2017-06",
                "files": [
                    {
                        "role": "article_pdf",
                        "title": "Final article PDF",
                        "local_path": "references/private/article.pdf",
                        "sha256": "a" * 64,
                        "access_note": "Legal personal research copy.",
                    }
                ],
            }
        )


def test_article_manifest_allows_blocked_article_only_manifest() -> None:
    manifest = ArticleManifest.model_validate(
        {
            "title": "Short-Term Interest Rates and Stock Market Anomalies",
            "authors": ["Paulo F. Maio", "Pedro Santa-Clara"],
            "doi": "10.1017/S002210901700028X",
            "journal": "Journal of Financial and Quantitative Analysis",
            "volume": "52",
            "issue": "3",
            "pages": "927-961",
            "publication_date": "2017-06",
            "status": "blocked_missing_supplement",
            "files": [
                {
                    "role": "article_pdf",
                    "title": "Final article PDF",
                    "local_path": "references/private/maio2017.pdf",
                    "sha256": "a" * 64,
                    "access_note": "Legal personal research copy.",
                }
            ],
            "missing_roles": ["supplement"],
        }
    )

    assert manifest.status == "blocked_missing_supplement"


def test_committed_article_manifest_records_publication_evidence() -> None:
    manifest = load_article_manifest(Path("artifacts/evidence/article_manifest.json"))

    checksums = {file.role: file.sha256 for file in manifest.files}

    assert manifest.status == "complete"
    assert manifest.file_roles == {"article_pdf", "supplement"}
    assert checksums == {
        "article_pdf": "2666ea25fb1cb2dde9d7e613c088a649757422e0ed44384008143e5424f72fda",
        "supplement": "576bad1d91202338729804b2dad86e2dfb6309fae6e9605c31f49c3d1e0f6e10",
    }


def test_table_targets_remain_unique_and_located() -> None:
    manifest_path = Path("research/table_target_manifest.csv")
    with manifest_path.open(encoding="utf-8", newline="") as manifest:
        rows = list(csv.DictReader(manifest))

    target_ids = [row["target_id"] for row in rows]
    source_locations = [row["source_location"] for row in rows]

    assert len(target_ids) == len(set(target_ids))
    assert all(source_locations)


def test_table_targets_have_article_frozen_ids() -> None:
    manifest_path = Path("research/table_target_manifest.csv")
    with manifest_path.open(encoding="utf-8", newline="") as manifest:
        rows = list(csv.DictReader(manifest))

    assert rows
    assert all(not row["target_id"].startswith("TBD") for row in rows)
    assert all(
        row["source_location"].startswith(("article_pdf:", "supplement_zip:")) for row in rows
    )
    assert any(row["target_id"] == "APP_TBL_A14" for row in rows)
