from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from app.domain.models import EvidenceItem
from app.research.evidence import content_hash, grade_evidence


class GitHubReleaseCollector:
    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def collect(self, repositories: list[str]) -> list[EvidenceItem]:
        if self._client is not None:
            return await self._collect_with_client(self._client, repositories)
        headers = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            timeout=30,
            headers=headers,
        ) as client:
            return await self._collect_with_client(client, repositories)

    async def _collect_with_client(
        self, client: httpx.AsyncClient, repositories: list[str]
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        observed_at = datetime.now(UTC)
        for repository in repositories:
            response = await client.get(f"/repos/{repository}/releases/latest")
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            published_at = datetime.fromisoformat(
                str(payload["published_at"]).replace("Z", "+00:00")
            ).astimezone(UTC)
            tag = str(payload.get("tag_name") or payload.get("name") or "release")
            release_url = str(payload["html_url"])
            raw_identity = {
                "repository": repository,
                "release_id": payload.get("id"),
                "tag": tag,
                "published_at": payload.get("published_at"),
                "url": release_url,
            }
            body = str(payload.get("body") or "").strip()
            items.append(
                EvidenceItem(
                    evidence_id=(
                        f"github-release-{repository.replace('/', '-')}-"
                        f"{payload.get('id')}"
                    ),
                    title=f"{repository} {tag}",
                    source_type="official_project_release",
                    source_url=release_url,
                    grade=grade_evidence("official_project_release"),
                    observed_at=observed_at,
                    event_date=published_at,
                    entity=repository,
                    summary=body[:1000] or f"Official release {tag}.",
                    content_hash=content_hash(raw_identity),
                    tags=["software-release"],
                    metadata={"repository": repository, "tag": tag},
                )
            )
        return items
