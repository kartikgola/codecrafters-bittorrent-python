from dataclasses import dataclass
from typing import Optional

@dataclass()
class Peer:
    id: bytes
    ip: str
    port: int
    supports_extensions: bool = False
    extension_metadata: Optional[dict] = None