"""Evidence-manifest models for article and supplement files."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from short_rate_anomaly_regimes.config import load_yaml


class EvidenceFile(BaseModel):
    """One legally obtained private evidence file."""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern="^(article_pdf|supplement)$")
    title: str
    local_path: str
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    access_note: str


class ArticleManifest(BaseModel):
    """Publication metadata and private evidence-file hashes."""

    model_config = ConfigDict(extra="forbid")

    title: str
    authors: list[str]
    doi: str
    journal: str
    volume: str
    issue: str
    pages: str
    publication_date: str
    files: list[EvidenceFile]

    @model_validator(mode="after")
    def validate_required_files(self) -> ArticleManifest:
        """Require both private evidence files before a manifest is accepted."""
        required_roles = {"article_pdf", "supplement"}
        missing_roles = required_roles - self.file_roles
        if missing_roles:
            missing = ", ".join(sorted(missing_roles))
            raise ValueError(f"Missing required evidence roles: {missing}")
        return self

    @property
    def file_roles(self) -> set[str]:
        """Return the set of evidence roles present in the manifest."""
        return {file.role for file in self.files}


def load_article_manifest(path: Path) -> ArticleManifest:
    """Load and validate an article evidence manifest from YAML-compatible syntax."""
    return ArticleManifest.model_validate(load_yaml(path))
