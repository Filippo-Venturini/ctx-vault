import json
from pathlib import Path
from ctxvault.core.exceptions import SkillNotFoundError
from ctxvault.models.vaults import Skill, VaultOperation
import frontmatter
from datetime import datetime
from ctxvault.core.vaults.base import BaseVault
from ctxvault.models.documents import SkillDocumentInfo

INDEX_FILE = "skills-index.json"

class SkillVault(BaseVault):
    supported_operations = frozenset({
        VaultOperation.INDEX,
        VaultOperation.WRITE,
        VaultOperation.LIST_SKILLS,
        VaultOperation.READ_SKILL,
    })

    @property
    def _index_path(self) -> Path:
        return self.vault_path / INDEX_FILE

    def _load_index(self) -> dict:
        if not self._index_path.exists():
            return {}
        return json.loads(self._index_path.read_text())

    def _save_index(self, index: dict) -> None:
        self._index_path.write_text(json.dumps(index, indent=2))

    def _rebuild_index(self) -> tuple[dict, list[str]]:
        """Scan all .md files and rebuild index. Returns (index, conflicts)."""
        index = {}
        conflicts = []

        for md_file in self.vault_path.glob("*.md"):
            if md_file.name == INDEX_FILE or md_file.name.startswith("."):
                continue
            post = frontmatter.load(md_file)
            name = post.get("name", md_file.stem)
            name_key = name.lower()

            if name_key in index:
                conflicts.append(name)
            else:
                index[name_key] = {
                    "name": name,
                    "file": md_file.name,
                    "description": post.get("description")
                }

        return index, conflicts

    def index_files(self, path: str | None = None) -> tuple[list[str], list[str]]:
        index, conflicts = self._rebuild_index()
        self._save_index(index)
        indexed = [v["file"] for v in index.values()]
        skipped = [f"Conflict: skill '{n}' appears in multiple files" for n in conflicts]
        return indexed, skipped

    def read_skill(self, skill_name: str) -> Skill:
        index = self._load_index()
        entry = index.get(skill_name.lower())
        if not entry:
            raise SkillNotFoundError(f"Skill '{skill_name}' not found.")
        
        file_path = self.vault_path / entry["file"]
        post = frontmatter.load(file_path)
        return Skill(
            name=entry["name"],
            description=entry["description"],
            instructions=post.content,
            metadata=None,
            path=file_path
        )

    def write_file(self, file_path: str, content: str, overwrite: bool = True, agent_metadata: dict | None = None) -> None:
        super().write_file(file_path=file_path, content=content, overwrite=overwrite)
        
        post = frontmatter.loads(content)
        name = post.get("name", Path(file_path).stem)
        index = self._load_index()
        index[name.lower()] = {
            "name": name,
            "file": Path(file_path).name,
            "description": post.get("description")
        }
        self._save_index(index)

    def list_skills(self) -> list[SkillDocumentInfo]:
        index = self._load_index()
        result = []
        for entry in index.values():
            file_path = self.vault_path / entry["file"]
            stats = file_path.stat()
            result.append(SkillDocumentInfo(
                source=entry["file"],
                filetype=".md",
                size_bytes=stats.st_size,
                skill_name=entry["name"],
                description=entry["description"],
                last_modified=datetime.fromtimestamp(stats.st_mtime).isoformat()
            ))
        return result