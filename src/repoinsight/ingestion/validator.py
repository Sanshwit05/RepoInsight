"""Repository URL validation and parsing module"""

from __future__ import annotations
import re
from dataclasses import dataclass

class InvalidRepositoryURLError(ValueError):
    """Raised when a repository URL is invalid or malformed."""

@dataclass(frozen=True)
class RepositoryTarget:
    """Immutable domain representation of a validated repository target."""
    raw_url: str
    host: str
    owner: str
    repo_name: str

    @property
    def canonical_url(self) -> str:
        """Standardized HTTPS URL for the repository."""
        return f"https://{self.host}/{self.owner}/{self.repo_name}"

    @property
    def clone_url(self) -> str:
        """HTTPS clone URL with .git extension."""
        return f"{self.canonical_url}.git"

    @property
    def identifier(self) -> str:
        """Unique slug identifier in the form 'owner/repo_name'."""
        return f"{self.owner}/{self.repo_name}"

_REPO_URL_PATTERN = re.compile(r"^(?:https?://|git@)(?P<host>[a-zA-Z0-9.-]+)(?::|/)(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+?)(?:\.git)?/?$")

def parse_repository_url(url: str) -> RepositoryTarget:
    """Validate and parse a Git repository URL into structured metadata.
    Args:
        url: The repository URL in HTTPS or SSH format.
    Returns:
        RepositoryTarget: A structured, immutable object containing parsed metadata.
    Raises:
        InvalidRepositoryURLError: If the URL format is empty, invalid, or unrecognized.
    """
    clean_url = url.strip()
    if not clean_url:
        raise InvalidRepositoryURLError("Repository URL cannot be empty.")

    match = _REPO_URL_PATTERN.match(clean_url)
    if not match: 
        raise InvalidRepositoryURLError(f"Invalid repository URL '{url}'. Expected format like "
            "'https://github.com/owner/repo' or 'git@github.com:owner/repo.git'.")

    host = match.group("host").lower()
    owner = match.group("owner")
    repo_name = match.group("repo")
    if "." not in host:
        raise InvalidRepositoryURLError(f"Invalid host '{host}' in repository URL '{url}'.")

    return RepositoryTarget(
        raw_url=clean_url,
        host=host,
        owner=owner,
        repo_name=repo_name
    )

if __name__ == "__main__":
    test_urls = [
         "https://github.com/pallets/flask",
        "https://github.com/psf/requests.git",
        "git@github.com:fastapi/fastapi.git",
        "https://github.com/tiangolo/typer/",
    ]
    print("--- Running Repository URL Validation Tests ---")
    for test_url in test_urls:
        target = parse_repository_url(test_url)
        print(f"[OK] Parsed: '{test_url}'")
        print(f"     Identifier : {target.identifier}")
        print(f"     Canonical  : {target.canonical_url}")
        print(f"     Clone URL  : {target.clone_url}\n")