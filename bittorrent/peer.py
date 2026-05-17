from dataclasses import dataclass

@dataclass(frozen=True)
class Peer:
    id: bytes
    ip: str
    port: int
    supports_extensions: bool = False