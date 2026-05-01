BitTorrent module implements the BitTorrent protocol and provides a high-level interface for working with torrents.

## Features
- Adding a torrent
- Removing a torrent
- Starting a torrent
- Stopping a torrent
- Listing all torrents
- Getting a torrent

## Usage

```python
from bittorrent.client import BitTorrentClient
from bittorrent.torrent import Torrent

client = BitTorrentClient()
torrent = Torrent("path/to/torrent")
client.add_torrent(torrent)
client.start_torrent(torrent)
```

## Entities
### 1. Torrent
- Represents a torrent file object.
- Torrent is used to load a `.torrent` file.
- Provides props like `info_hash`, `piece_length`, etc.

### 2. BittorrentClient
- Boring user facing interface to expose methods.

### 3. Peer
- Represents a bittorrent peer.

### 4. PeerConnection
- Represents a connection to the peer.
- This class knows how to "talk" to the peer.

### 5. ConnectionManager
- For orchestration of the peer connections.

### 6. TrackerClient
- Interacts with a torrent's tracker
