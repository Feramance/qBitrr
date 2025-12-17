# Multi-qBittorrent Instance Support - Implementation Plan v3.0

## Executive Summary

Enable qBitrr to **monitor and manage multiple qBittorrent instances simultaneously**. Each Arr instance (Radarr/Sonarr/Lidarr) configures its own download clients, and qBitrr discovers torrents across ALL instances for health checks, import triggering, and cleanup.

**Key Principle**: Radarr/Sonarr/Lidarr handle download client selection. qBitrr monitors all configured qBit instances equally.

---

## Architecture Overview

### Current State (Single qBit)
```
Radarr → Download Client Config → qBittorrent
                                       ↓
                                   qBitrr monitors torrents (health, import, cleanup)
```

### New State (Multi qBit - Equal Instances)
```
Radarr → Download Client 1 → qBit-1
      → Download Client 2 → qBit-2    } qBitrr monitors ALL instances simultaneously
      → Download Client 3 → qBit-3
                                ↓
                    Health checks, imports, cleanup on correct instance
```

### Core Concept

- **Arr-Managed Routing**: Radarr/Sonarr/Lidarr decide which qBit instance to use (via their download client configuration)
- **Equal Instance Monitoring**: qBitrr treats all instances equally; no "primary" concept
- **Instance Discovery**: qBitrr scans ALL instances for torrents with matching category tags
- **Instance-Aware Operations**: Health checks, imports, and cleanup happen on the correct instance

---

## Configuration Schema

### Multiple qBit Instances (Equal Status)

```toml
[Settings]
ConfigVersion = 4
# ... existing settings ...

# Default qBittorrent instance
[qBit]
Disabled = false
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "password"

# Additional instances (equal to default)
[qBit-Seedbox]
Host = "seedbox.example.com"
Port = 8080
UserName = "seedbox_user"
Password = "seedbox_pass"

[qBit-Server2]
Host = "192.168.1.100"
Port = 8090
UserName = "server2_user"
Password = "server2_pass"

# Arr configuration (NO instance selection - Arr handles this via download clients)
[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "..."
Category = "radarr"
# qBitrr will monitor ALL instances for torrents tagged "radarr"

[Sonarr-TV]
Managed = true
URI = "http://localhost:8989"
APIKey = "..."
Category = "sonarr"
# qBitrr will monitor ALL instances for torrents tagged "sonarr"
```

### Important Notes

1. **No routing fields**: No `Priority`, `AllowedCategories`, or `qBitInstance` fields
2. **Arr download clients**: Configure multiple download clients in Radarr/Sonarr pointing to different qBit instances
3. **Same category, multiple instances**: The same category (e.g., "radarr") can exist on multiple qBit instances
4. **Database tracking**: Each torrent tracked with `(Hash, QbitInstance)` tuple

---

## Implementation Phases

### Phase 1: Database Schema Updates (4-6 hours)

#### 1.1 Update Database Models

**File: `qBitrr/tables.py`**

```python
class TorrentLibrary(Model):
    Hash = CharField(unique=False)  # Changed: no longer globally unique!
    Category = CharField()
    QbitInstance = CharField(default="default")  # NEW: track which instance

    # ... existing fields (Name, ContentPath, etc.) ...

    class Meta:
        database = db
        # NEW: Compound unique constraint (hash unique per instance)
        indexes = (
            (('Hash', 'QbitInstance'), True),  # Unique constraint
        )
```

**✅ No Migration Logic Needed:**

Per user constraint: qBitrr databases are recreated on restart/update. The new schema will be applied automatically when users upgrade. No ALTER TABLE or migration code is required.

#### 1.2 Update All Database Queries

All queries that reference `TorrentLibrary.Hash` must now include instance context:

```python
# OLD (single instance)
torrent = TorrentLibrary.get(TorrentLibrary.Hash == hash_value)

# NEW (multi-instance)
torrent = TorrentLibrary.get(
    (TorrentLibrary.Hash == hash_value) &
    (TorrentLibrary.QbitInstance == instance_name)
)

# OLD (delete by hash)
TorrentLibrary.delete().where(TorrentLibrary.Hash == hash_value).execute()

# NEW (delete by hash + instance)
TorrentLibrary.delete().where(
    (TorrentLibrary.Hash == hash_value) &
    (TorrentLibrary.QbitInstance == instance_name)
).execute()
```

---

### Phase 2: qBitManager Multi-Instance Support (16-24 hours)

#### 2.1 Core Refactoring

**File: `qBitrr/main.py`**

```python
class qBitManager:
    min_supported_version = VersionClass("4.3.9")
    soft_not_supported_supported_version = VersionClass("4.4.4")
    _head_less_mode = False

    def __init__(self):
        self._name = "Manager"
        self.shutdown_event = Event()

        # NEW: Dictionary of clients keyed by instance name
        self.clients: dict[str, qbittorrentapi.Client] = {}

        # NEW: Dictionary of versions per instance
        self.qbit_versions: dict[str, VersionClass] = {}

        # NEW: Instance metadata (host, port)
        self.instance_metadata: dict[str, dict[str, Any]] = {}

        # NEW: Health tracking per instance
        self.instance_health: dict[str, bool] = {}

        # Default instance name for backward compatibility
        self.default_instance = "default"

        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        run_logs(self.logger, self._name)

        # Initialize all qBit instances
        if not (QBIT_DISABLED or SEARCH_ONLY):
            self._initialize_qbit_instances()

            # Backward compatibility: point to default instance
            self.client = self.clients.get(self.default_instance)
            self.current_qbit_version = self.qbit_versions.get(self.default_instance)
        else:
            self.client = None
            self.current_qbit_version = None

        # ... rest of existing init ...

    def _initialize_qbit_instances(self):
        """Initialize all configured qBittorrent instances"""
        # Primary [qBit] instance
        self._init_instance("qBit", self.default_instance)

        # Additional instances (qBit-XXX sections)
        for section_name in CONFIG.sections():
            if section_name.startswith("qBit-"):
                instance_name = section_name  # Use full section name as instance key
                self._init_instance(section_name, instance_name)

    def _init_instance(self, section_name: str, instance_name: str):
        """Initialize a single qBit instance"""
        try:
            host = CONFIG.get(f"{section_name}.Host", fallback="localhost")
            port = CONFIG.get(f"{section_name}.Port", fallback=8080)
            username = CONFIG.get(f"{section_name}.UserName", fallback=None)
            password = CONFIG.get(f"{section_name}.Password", fallback=None)

            client = qbittorrentapi.Client(
                host=host,
                port=port,
                username=username,
                password=password,
                SIMPLE_RESPONSES=False,
            )

            # Test connection and get version
            try:
                version = version_parser.parse(client.app_version())
                self._validate_version(version, instance_name)
            except Exception as e:
                self.logger.error(
                    "Could not establish qBit version for instance '%s' (%s): %s",
                    instance_name, f"{host}:{port}", e
                )
                version = self.min_supported_version

            # Store client and metadata
            self.clients[instance_name] = client
            self.qbit_versions[instance_name] = version
            self.instance_metadata[instance_name] = {
                "host": host,
                "port": port,
                "section": section_name,
            }
            self.instance_health[instance_name] = True

            self.logger.info(
                "Initialized qBit instance '%s' at %s:%s (version: %s)",
                instance_name, host, port, version
            )
        except Exception as e:
            self.logger.error(
                "Failed to initialize qBit instance '%s': %s",
                instance_name, e
            )

    def _validate_version(self, version: VersionClass, instance_name: str):
        """Validate qBit version for an instance"""
        if version < self.min_supported_version:
            self.logger.critical(
                "qBit instance '%s' is running version %s which is not supported. "
                "Minimum version is %s",
                instance_name, version, self.min_supported_version
            )
            sys.exit(1)
        else:
            self.logger.debug(
                "qBit instance '%s' version %s is supported",
                instance_name, version
            )

    def is_instance_alive(self, instance_name: str) -> bool:
        """Check if a specific qBit instance is alive"""
        client = self.clients.get(instance_name)
        if not client:
            return False

        try:
            client.app_version()
            self.instance_health[instance_name] = True
            return True
        except requests.RequestException:
            self.instance_health[instance_name] = False
            meta = self.instance_metadata.get(instance_name, {})
            self.logger.warning(
                "Cannot connect to qBit instance '%s' at %s:%s",
                instance_name, meta.get("host"), meta.get("port")
            )
            return False

    def get_all_instances(self) -> list[str]:
        """Get list of all configured instance names"""
        return list(self.clients.keys())

    @property
    def is_alive(self) -> bool:
        """Check if default instance is alive (backward compatibility)"""
        return self.is_instance_alive(self.default_instance)
```

---

### Phase 3: Arr Class Updates (24-32 hours)

#### 3.1 Multi-Instance Torrent Monitoring

**File: `qBitrr/arss.py`**

Update `Arr.__init__` to ensure category exists on ALL instances:

```python
class Arr:
    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_cls: type[Callable | RadarrAPI | SonarrAPI | LidarrAPI],
    ):
        # ... existing init code ...

        if not QBIT_DISABLED:
            # NEW: Ensure category exists on ALL qBit instances
            self._ensure_category_on_all_instances()

        # ... rest of init ...

    def _ensure_category_on_all_instances(self):
        """Ensure this Arr's category exists on all qBit instances"""
        for instance_name in self.manager.qbit_manager.get_all_instances():
            client = self.manager.qbit_manager.clients.get(instance_name)
            if not client:
                continue

            try:
                categories = client.torrent_categories.categories
                if self.category not in categories:
                    client.torrent_categories.create_category(
                        self.category,
                        save_path=str(self.completed_folder)
                    )
                    self.logger.info(
                        "Created category '%s' on qBit instance '%s'",
                        self.category, instance_name
                    )
                else:
                    self.logger.trace(
                        "Category '%s' already exists on qBit instance '%s'",
                        self.category, instance_name
                    )
            except Exception as e:
                self.logger.warning(
                    "Failed to create/verify category '%s' on instance '%s': %s",
                    self.category, instance_name, e
                )
```

#### 3.2 Update Torrent Processing Loop

The main torrent loop must now iterate over ALL instances:

```python
def process_torrents_multi_instance(self):
    """Process torrents across ALL qBit instances"""
    all_instances = self.manager.qbit_manager.get_all_instances()

    for instance_name in all_instances:
        client = self.manager.qbit_manager.clients.get(instance_name)
        if not client:
            continue

        # Check if instance is alive
        if not self.manager.qbit_manager.is_instance_alive(instance_name):
            self.logger.warning(
                "Skipping qBit instance '%s' (not responding)",
                instance_name
            )
            continue

        try:
            # Get torrents for this category on this instance
            torrents = client.torrents.info(category=self.category)
            self.logger.trace(
                "Found %d torrent(s) in category '%s' on instance '%s'",
                len(torrents), self.category, instance_name
            )

            # Process each torrent with instance context
            for torrent in torrents:
                self._process_single_torrent(torrent, instance_name, client)

        except Exception as e:
            self.logger.error(
                "Error processing torrents on instance '%s': %s",
                instance_name, e
            )
```

#### 3.3 Update Individual Torrent Operations

All torrent operations must now pass instance context:

```python
def _process_single_torrent(
    self,
    torrent: TorrentDictionary,
    instance_name: str,
    client: qbittorrentapi.Client
):
    """Process a single torrent with instance context"""
    hash_value = torrent.hash

    # Update/create database entry with instance
    self._update_torrent_db(hash_value, instance_name, torrent)

    # Existing processing logic (health checks, imports, etc.)
    # All operations use the provided client and instance_name
    # ...

def _update_torrent_db(
    self,
    hash_value: str,
    instance_name: str,
    torrent: TorrentDictionary
):
    """Update database with torrent info, including instance"""
    try:
        # Try to get existing entry
        entry = TorrentLibrary.get(
            (TorrentLibrary.Hash == hash_value) &
            (TorrentLibrary.QbitInstance == instance_name)
        )
        # Update existing entry
        entry.Category = torrent.category
        entry.save()
    except TorrentLibrary.DoesNotExist:
        # Create new entry
        TorrentLibrary.create(
            Hash=hash_value,
            QbitInstance=instance_name,
            Category=torrent.category,
            Name=torrent.name,
            ContentPath=torrent.content_path,
            # ... other fields ...
        )

def _remove_torrent(self, hash_value: str, instance_name: str):
    """Remove torrent from qBit and database"""
    client = self.manager.qbit_manager.clients.get(instance_name)
    if not client:
        self.logger.error(
            "Cannot remove torrent %s: instance '%s' not found",
            hash_value[:8], instance_name
        )
        return

    # Remove from qBit
    try:
        client.torrents_delete(delete_files=True, torrent_hashes=hash_value)
        self.logger.info(
            "Removed torrent %s from instance '%s'",
            hash_value[:8], instance_name
        )
    except Exception as e:
        self.logger.error(
            "Failed to remove torrent %s from instance '%s': %s",
            hash_value[:8], instance_name, e
        )

    # Remove from database
    TorrentLibrary.delete().where(
        (TorrentLibrary.Hash == hash_value) &
        (TorrentLibrary.QbitInstance == instance_name)
    ).execute()
```

---

### Phase 4: WebUI Backend Updates (10-14 hours)

#### 4.1 Status Endpoint

**File: `qBitrr/webui.py`**

```python
def _status_payload() -> dict[str, Any]:
    """Return status of all qBit instances and Arr instances"""

    # All qBit instances
    qbit_instances = {}
    for instance_name, client in manager.qbit_manager.clients.items():
        metadata = manager.qbit_manager.instance_metadata.get(instance_name, {})
        is_alive = manager.qbit_manager.is_instance_alive(instance_name)
        version = manager.qbit_manager.qbit_versions.get(instance_name)

        qbit_instances[instance_name] = {
            "name": instance_name,
            "alive": is_alive,
            "host": metadata.get("host"),
            "port": metadata.get("port"),
            "version": str(version) if version else None,
        }

    # Arr instances
    arrs = []
    for category, arr in _managed_objects().items():
        arr_type = getattr(arr, "type", None)
        if arr_type in ("radarr", "sonarr", "lidarr"):
            # ... existing alive check ...

            arrs.append({
                "category": category,
                "name": getattr(arr, "_name", category),
                "type": arr_type,
                "alive": alive,
            })

    return {
        "qbit": qbit_instances.get("default", {}),  # Backward compat
        "qbitInstances": qbit_instances,
        "arrs": arrs,
        "ready": _ensure_arr_manager_ready()
    }
```

#### 4.2 Torrent Distribution Endpoint

```python
@app.get("/api/torrents/distribution")
def api_torrent_distribution():
    """Get torrent distribution across qBit instances"""
    if (resp := require_token()) is not None:
        return resp

    distribution = {}

    for instance_name, client in manager.qbit_manager.clients.items():
        try:
            torrents = client.torrents.info()

            # Group by category
            by_category = {}
            for t in torrents:
                cat = t.category or "uncategorized"
                by_category[cat] = by_category.get(cat, 0) + 1

            # Get instance metadata
            meta = manager.qbit_manager.instance_metadata.get(instance_name, {})

            distribution[instance_name] = {
                "total": len(torrents),
                "by_category": by_category,
                "alive": manager.qbit_manager.is_instance_alive(instance_name),
                "host": meta.get("host"),
                "port": meta.get("port"),
            }
        except Exception as e:
            distribution[instance_name] = {
                "error": str(e),
                "alive": False
            }

    return jsonify({"distribution": distribution})
```

---

### Phase 5: Frontend Updates (12-18 hours)

#### 5.1 TypeScript Types

**File: `webui/src/api/types.ts`**

```typescript
export interface QbitInstance {
  name: string;
  alive: boolean;
  host: string | null;
  port: number | null;
  version: string | null;
}

export interface QbitStatusResponse {
  qbit: QbitInstance;  // Default instance (backward compat)
  qbitInstances: Record<string, QbitInstance>;
  arrs: ArrInfo[];
  ready: boolean;
}

export interface TorrentDistribution {
  distribution: Record<string, {
    total: number;
    by_category: Record<string, number>;
    alive: boolean;
    host: string;
    port: number;
    error?: string;
  }>;
}
```

#### 5.2 QbitInstancesView Component

**File: `webui/src/pages/QbitInstancesView.tsx`**

```typescript
import { useEffect, useState } from 'react';
import { Card, Badge, Group, Stack, Text, Title, SimpleGrid } from '@mantine/core';
import { getStatus } from '../api/api';
import { QbitInstance, TorrentDistribution } from '../api/types';

export function QbitInstancesView({ active }: { active: boolean }) {
  const [instances, setInstances] = useState<QbitInstance[]>([]);
  const [distribution, setDistribution] = useState<TorrentDistribution | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (active) {
      loadData();
      const interval = setInterval(loadData, 5000);  // Refresh every 5s
      return () => clearInterval(interval);
    }
  }, [active]);

  const loadData = async () => {
    try {
      const [statusData, distData] = await Promise.all([
        getStatus(),
        fetch("/api/torrents/distribution").then(r => r.json())
      ]);

      setInstances(Object.values(statusData.qbitInstances));
      setDistribution(distData);
    } catch (error) {
      console.error("Failed to load qBit instances:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Text>Loading qBittorrent instances...</Text>;
  }

  return (
    <Stack gap="md">
      <Title order={2}>qBittorrent Instances</Title>

      <SimpleGrid cols={2} spacing="md">
        {instances.map((instance) => {
          const distData = distribution?.distribution[instance.name];

          return (
            <Card key={instance.name} withBorder shadow="sm">
              <Group justify="space-between" mb="xs">
                <div>
                  <Text fw={600} size="lg">{instance.name}</Text>
                  <Text size="sm" c="dimmed">
                    {instance.host}:{instance.port}
                  </Text>
                  {instance.version && (
                    <Text size="xs" c="dimmed">
                      Version: {instance.version}
                    </Text>
                  )}
                </div>
                <Badge color={instance.alive ? "green" : "red"} size="lg">
                  {instance.alive ? "Online" : "Offline"}
                </Badge>
              </Group>

              {distData && !distData.error && (
                <Stack gap="xs" mt="md">
                  <Text fw={500}>
                    Total Torrents: {distData.total}
                  </Text>
                  {Object.entries(distData.by_category).map(([cat, count]) => (
                    <Group key={cat} justify="space-between">
                      <Text size="sm">{cat}</Text>
                      <Badge variant="light">{count}</Badge>
                    </Group>
                  ))}
                </Stack>
              )}

              {distData?.error && (
                <Text c="red" size="sm" mt="md">
                  Error: {distData.error}
                </Text>
              )}
            </Card>
          );
        })}
      </SimpleGrid>
    </Stack>
  );
}
```

---

### Phase 6: Config Migration & Testing (6-8 hours)

#### 6.1 Config Migration (Database Migration NOT Needed)

**✅ User Constraint: Databases recreated on restart/update**

Database migration code is NOT required because:
- qBitrr databases are SQLite files that get recreated on version changes
- New schema will be applied automatically via Peewee model definitions
- Existing torrents will be rediscovered and repopulated with new schema

**Config migration may still be needed:**

**File: `qBitrr/config.py`** (if ConfigVersion bump is needed)

```python
def _migrate_config_v3_to_v4(config: MyConfig) -> None:
    """
    Migrate config from v3 to v4 (multi-qBit support).

    Changes:
    - No config file changes required (100% backward compatible)
    - Database schema updated automatically (no migration code needed)
    - Log informational message about multi-qBit support
    """
    from qBitrr.config_version import get_config_version

    current_version = get_config_version(config)
    if current_version >= 4:
        return

    # No actual migration needed - just bump version and inform user
    print("✓ Config migrated v3→v4: Multi-qBittorrent support enabled")
    print("  - Database schema will be automatically updated")
    print("  - Add [qBit-Name] sections to config for additional instances")
    print("  - Configure multiple download clients in Radarr/Sonarr")
    print("  - qBitrr will monitor ALL configured instances equally")
```

**Update ConfigVersion:**

**File: `qBitrr/config_version.py`**

```python
CURRENT_CONFIG_VERSION = 4  # Bumped for multi-qBit support
```

#### 6.2 Backward Compatibility

The implementation maintains 100% backward compatibility:

1. **Single instance configs**: Continue to work without changes
2. **`self.client` reference**: Points to default instance
3. **Existing API endpoints**: `/api/status` returns `qbit` field for default instance
4. **Database**: New instances use `QbitInstance = "default"` for backward compat
5. **No config changes**: Existing single-instance setups work as-is

---

## Summary of Architecture Changes

| Aspect | Current (v3) | New (v4) |
|--------|-------------|----------|
| **qBit Instances** | Single instance | Multiple instances (equal) |
| **Instance Selection** | N/A (only one) | Arr configures download clients |
| **Torrent Discovery** | Single scan | Scan ALL instances |
| **Database Schema** | Hash unique globally | Hash unique per instance |
| **Category Management** | One instance | Created on ALL instances |
| **Health Checks** | Single instance | Per-instance checks |
| **Import Triggering** | Single instance | Instance-aware |
| **Cleanup** | Single instance | Instance-specific |

---

## Configuration Examples

### Example 1: Simple Multi-Instance

```toml
[qBit]
Host = "localhost"
Port = 8080

[qBit-Seedbox]
Host = "seedbox.example.com"
Port = 8080

[Radarr-Movies]
Category = "radarr"
# Radarr configures 2 download clients pointing to localhost and seedbox
# qBitrr monitors both instances for "radarr" torrents
```

### Example 2: Three Instances

```toml
[qBit]
Host = "192.168.1.10"
Port = 8080

[qBit-Server2]
Host = "192.168.1.20"
Port = 8080

[qBit-Server3]
Host = "192.168.1.30"
Port = 8080

[Sonarr-TV]
Category = "sonarr"
# Sonarr distributes downloads across 3 servers
# qBitrr monitors all 3 for health/imports/cleanup
```

---

## Implementation Timeline

| Phase | Effort | Description |
|-------|--------|-------------|
| 1 | 4-6h | Database schema updates (no migration code needed) |
| 2 | 16-24h | qBitManager multi-instance initialization |
| 3 | 24-32h | Arr class updates (scan all instances) |
| 4 | 10-14h | WebUI backend updates |
| 5 | 12-18h | Frontend updates |
| 6 | 6-8h | Testing (no migration code needed) |
| **Total** | **72-102h** | **~2 weeks** |

---

## Testing Strategy

### Unit Tests
- Compound unique constraint (Hash, QbitInstance)
- Instance initialization (multiple clients)
- Health checking per instance
- Database queries with instance context

### Integration Tests
- Torrent discovery across instances
- Health checks on correct instance
- Import triggering with instance context
- Cleanup on correct instance
- Multiple Arr instances using same category

### Manual Tests
- Fresh install with 2+ qBit instances
- Upgrade from v3 (database recreated with new schema)
- One instance goes offline (others continue)
- Same torrent hash on different instances
- WebUI displays all instances correctly
- Single instance config still works (backward compat)

---

**Status**: ✅ Plan Complete - Ready for Implementation
**Version**: 3.0
**Architecture**: Equal Multi-Instance Monitoring
**Backward Compatible**: ✅ Yes (100% backward compatible)
**User Configuration**: Minimal (just add [qBit-Name] sections)
**Database Migration**: ❌ Not needed (DBs recreated on restart/update)
**Config Migration**: ⚠️ May be needed (for ConfigVersion bump only)
