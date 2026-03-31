from enum import Enum

class VaultType(Enum):
    SEMANTIC = "semantic"
    SKILL = "skill"

    @classmethod
    def list(cls):
        return [v.value for v in cls]