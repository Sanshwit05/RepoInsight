"""Domain models for Git history mining and commit telemetry."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class ChangeType(str, Enum):
    """Enumeration of file-level Git modification types."""

    ADD = "ADD"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    RENAME = "RENAME"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_str(cls, value: str | None) -> ChangeType:
        """Safely parse raw Git change type strings into enum values."""
        if not value:
            return cls.UNKNOWN
        normalized = value.strip().upper()
        return cls.__members__.get(normalized, cls.UNKNOWN)

@dataclass(frozen=True)
class FileChangeRecord:
    """Immutable record of an individual file modification within a commit."""
    old_path: str | None
    new_path: str | None
    change_type: ChangeType
    added_lines: int
    deleted_lines: int

    @property
    def path(self) -> str:
        """Return the current path (new_path if exists, otherwise old_path)."""
        return self.new_path or self.old_path or "unknown_path"

    @property
    def churn(self) -> int:
        """Total lines touched (added + deleted) in this file modification."""
        return self.added_lines + self.deleted_lines

@dataclass(frozen=True)
class CommitRecord:
    """Immutable record of a Git commit with associated file changes and metadata."""
    hash: str
    author_name: str
    author_email: str
    committed_at: datetime
    message: str
    is_merge: bool
    parents: tuple[str, ...] = field(default_factory=tuple)
    file_changes: tuple[FileChangeRecord, ...] = field(default_factory=tuple)

    @property
    def total_lines_added(self) -> int:
        """Aggregate lines added across all modified files."""
        return sum(fc.added_lines for fc in self.file_changes)

    @property
    def total_lines_deleted(self) -> int:
        """Aggregate lines deleted across all modified files."""
        return sum(fc.deleted_lines for fc in self.file_changes)
    
    @property
    def total_churn(self) -> int:
        """Aggregate code churn (added + deleted) across all modified files."""
        return self.total_lines_added + self.total_lines_deleted
    
    @property
    def modified_file_count(self) -> int:
        """Total number of files touched in this commit."""
        return len(self.file_changes)

if __name__ == "__main__":
    print("--- Demonstrating Mining Domain Models ---")
    change1 = FileChangeRecord(
        old_path="src/app.py",
        new_path="src/app.py",
        change_type=ChangeType.MODIFY,
        added_lines=25,
        deleted_lines=5,
    )
    change2 = FileChangeRecord(
        old_path=None,
        new_path="src/utils.py",
        change_type=ChangeType.ADD,
        added_lines=40,
        deleted_lines=0,
    )
    sample_commit = CommitRecord(
        hash="a1b2c3d4e5f67890123456789abcdef012345678",
        author_name="Alice Developer",
        author_email="alice@example.com",
        committed_at=datetime.utcnow(),
        message="feat: add utility module and update main app logic",
        is_merge=False,
        parents=("0000000000000000000000000000000000000000",),
        file_changes=(change1, change2),
    )
    print(f"[OK] Commit Hash       : {sample_commit.hash[:8]}")
    print(f"[OK] Author            : {sample_commit.author_name} <{sample_commit.author_email}>")
    print(f"[OK] Timestamp         : {sample_commit.committed_at.isoformat()}")
    print(f"[OK] Files Touched     : {sample_commit.modified_file_count}")
    print(f"[OK] Lines Added       : {sample_commit.total_lines_added}")
    print(f"[OK] Lines Deleted     : {sample_commit.total_lines_deleted}")
    print(f"[OK] Total Churn       : {sample_commit.total_churn}")
    for fc in sample_commit.file_changes:
        print(f"     -> {fc.change_type.value:6s} {fc.path:<15s} (+{fc.added_lines}, -{fc.deleted_lines})")
        