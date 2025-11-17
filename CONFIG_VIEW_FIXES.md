# Config View Fixes and Adjustments

## Overview
This document outlines all planned fixes and adjustments for the qBitrr WebUI Config View to address issues with loading, validation, editability, and naming conventions for Arr instances.

## Issues Identified

### 1. Seeding Settings Not Loading or Editable
**Problem**: Seeding settings appear "hard locked to 0" even when the config file contains different values.

**Root Cause**: 
- Current field paths use `["Torrent", "SeedingMode", "FieldName"]` (nested structure for newer configs)
- Existing/older configs store seeding settings directly under `["Torrent", "FieldName"]`
- Path mismatch causes `getValue()` to return `undefined`, displaying as 0 in the UI
- Changes save to the wrong path, creating inconsistencies

**Impact**: 
- Fields like `DownloadRateLimitPerTorrent`, `UploadRateLimitPerTorrent`, `MaxUploadRatio`, `MaxSeedingTime`, `RemoveTorrent` don't load from existing configs
- User edits don't persist correctly
- Creates duplicate entries in config or fails to update existing values

### 2. Section Visibility Inconsistency
**Problem**: All sections except main general fields should default to collapsed state.

**Current State**: Most sections are already collapsed, but needs verification and consistency.

### 3. Arr Instance Naming Conventions Not Enforced
**Problem**: Users can create Arr instances with arbitrary names, leading to inconsistencies.

**Required Behavior**:
- All Sonarr instances must start with "Sonarr"
- All Radarr instances must start with "Radarr"
- All Lidarr instances must start with "Lidarr"
- Users should be able to customize the suffix but not the prefix

### 4. Comprehensive Config Logic Validation
**Problem**: Need to ensure all config view logic properly handles validation, loading, and saving across all field types and sections.

**Scope**: 
- Review all field definitions for correct paths matching config structure
- Verify validation functions cover all edge cases
- Ensure loading logic handles missing values, type coercion, and nested structures
- Confirm saving logic preserves config structure and doesn't introduce inconsistencies
- Check all sections (Settings, WebUI, qBit, Arr instances, Trackers, etc.) for completeness

## Planned Fixes

### Fix 0: Comprehensive Config Logic Review

**Files**: 
- `webui/src/pages/ConfigView.tsx`
- `qBitrr/webui.py` (backend validation)
- `qBitrr/gen_config.py` (reference for correct structure)

**Action Items**:
1. **Field Path Verification**:
   - Audit all field definitions (`ARR_GENERAL_FIELDS`, `ARR_ENTRY_SEARCH_FIELDS`, `ARR_TORRENT_FIELDS`, `ARR_SEEDING_FIELDS`, `ARR_TRACKER_FIELDS`, `SETTINGS_FIELDS`, `WEBUI_FIELDS`, `QBIT_FIELDS`)
   - Verify paths match actual config structure (check against `gen_config.py` and existing configs)
   - Identify any other path mismatches similar to seeding fields issue

2. **Loading Logic Review**:
   - Test `getValue()` with nested objects, arrays, and missing values
   - Verify type coercion (number inputs, checkboxes, selects, text fields)
   - Ensure default values display correctly when config lacks a field
   - Check array handling (Trackers, PingURLs, etc.)

3. **Validation Coverage**:
   - Review all `validate` functions for completeness
   - Ensure number fields check for valid ranges (e.g., -1 allowed for disabled features)
   - Verify required field validation (URI, APIKey, etc.)
   - Check enum validation (Theme, ConsoleLevel, etc.)
   - Test edge cases (empty strings, null, undefined, negative numbers)

4. **Saving Logic Review**:
   - Verify `flatten()` correctly serializes all structures
   - Ensure `_toml_set()` in backend preserves config format
   - Test that unchanged fields aren't modified
   - Verify new fields are added correctly
   - Check that deletions (e.g., removing tracker) work properly

5. **Section-Specific Checks**:
   - **Settings**: All global settings load/save correctly
   - **WebUI**: Theme, Host, Port, Token, Live settings work
   - **qBit**: Connection settings, disabled mode
   - **Arr Instances**: All fields in general, EntrySearch, Torrent, Seeding, Trackers
   - **Quality Profile Mappings**: Dict-based mappings load/save correctly
   - **Ombi/Overseerr**: Integration settings work

6. **Edge Case Testing**:
   - Empty config → defaults populate correctly
   - Partial config → missing fields use defaults
   - Invalid values → validation prevents save
   - Protected keys → cannot be modified
   - Array manipulation → add/remove items works

**Deliverables**:
- Document any additional path mismatches found
- List any validation gaps
- Identify any loading/saving issues beyond seeding fields
- Create comprehensive test matrix for all field types

### Fix 1: Update Seeding Field Paths for Backward Compatibility

**File**: `webui/src/pages/ConfigView.tsx`

**Change**: Update `ARR_SEEDING_FIELDS` path definitions to load from `["Torrent", "FieldName"]` instead of `["Torrent", "SeedingMode", "FieldName"]`

**Updated Paths**:
```typescript
const ARR_SEEDING_FIELDS: FieldDefinition[] = [
  {
    label: "Download Rate Limit Per Torrent",
    path: ["Torrent", "DownloadRateLimitPerTorrent"],  // Changed from ["Torrent", "SeedingMode", "DownloadRateLimitPerTorrent"]
    type: "number",
    // ... validation unchanged
  },
  {
    label: "Upload Rate Limit Per Torrent",
    path: ["Torrent", "UploadRateLimitPerTorrent"],  // Changed
    type: "number",
    // ... validation unchanged
  },
  {
    label: "Max Upload Ratio",
    path: ["Torrent", "MaxUploadRatio"],  // Changed
    type: "number",
    // ... validation unchanged
  },
  {
    label: "Max Seeding Time (s)",
    path: ["Torrent", "MaxSeedingTime"],  // Changed
    type: "number",
    // ... validation unchanged
  },
  {
    label: "Remove Torrent",
    path: ["Torrent", "RemoveTorrent"],  // Changed
    type: "number",
    // ... validation unchanged
  },
  {
    label: "Remove Dead Trackers",
    path: ["Torrent", "RemoveDeadTrackers"],  // Changed
    type: "checkbox",
  },
  {
    label: "Remove Tracker Messages",
    path: ["Torrent", "RemoveTrackerWithMessage"],  // Changed
    type: "text",
    fullWidth: true,
  },
];
```

**Benefits**:
- Loads values from existing config structure without migration
- Saves back to the same location, preserving config format
- No breaking changes to existing configs
- Maintains backward compatibility

**Note**: This matches the structure in `qBitrr/gen_config.py:_gen_default_seeding_table()` which adds seeding fields under `torrent_table.add("SeedingMode", seeding_table)` but the fields are accessible as `Torrent.SeedingMode.FieldName` in TOML. However, flattened or older configs may have them directly under `Torrent`. The UI should match the actual storage location.

### Fix 2: Verify Section Visibility Defaults

**File**: `webui/src/pages/ConfigView.tsx`

**Change**: Ensure all sections in `ArrInstanceModal` follow the rule:
- Main general fields: `defaultOpen={true}` (already present)
- Entry Search: `defaultOpen={true}` (already present)
- Quality Profile Mappings: `defaultOpen={true}` (already present)
- All others (Ombi, Overseerr, Torrent Handling, Seeding, Trackers): collapsed by default (no `defaultOpen` prop or `defaultOpen={false}`)

**Verification**: Review all `FieldGroup` components in modals to ensure consistency.

### Fix 3: Enforce Arr Instance Naming Conventions

**File**: `webui/src/pages/ConfigView.tsx`

#### 3a. Auto-Generate Names on Add

**Change**: Update `handleAddArr` to accept a type parameter and auto-generate names with the correct prefix.

**New Helper Function**:
```typescript
function generateArrName(type: string, existingKeys: string[]): string {
  // Normalize type to PascalCase prefix
  const prefix = type.charAt(0).toUpperCase() + type.slice(1).toLowerCase(); // "Radarr", "Sonarr", "Lidarr"
  
  // Find existing instances with this prefix
  const existingInstances = existingKeys.filter(key => key.startsWith(prefix));
  
  // Extract numbers from existing names (e.g., "Radarr-1" -> 1)
  const numbers = existingInstances
    .map(key => {
      const match = key.match(new RegExp(`^${prefix}-(\\d+)$`));
      return match ? parseInt(match[1], 10) : null;
    })
    .filter((num): num is number => num !== null);
  
  // Generate next available number
  const nextNum = numbers.length > 0 ? Math.max(...numbers) + 1 : 1;
  
  return `${prefix}-${nextNum}`;
}
```

**Updated `handleAddArr`**:
```typescript
const handleAddArr = (type: string) => {
  const existingKeys = Object.keys(formState);
  const keyName = generateArrName(type, existingKeys);
  
  setFormState(produce(formState, (draft) => {
    draft[keyName] = ensureArrDefaults(keyName);
  }));
  
  setActiveArrKey(keyName);
};
```

**Update UI Buttons**:
```typescript
// In ConfigView render, update buttons to pass type instead of fixed name:
<button onClick={() => handleAddArr("radarr")}>
  <IconImage src={RadarrIcon} />
  Add Radarr
</button>
<button onClick={() => handleAddArr("sonarr")}>
  <IconImage src={SonarrIcon} />
  Add Sonarr
</button>
<button onClick={() => handleAddArr("lidarr")}>
  <IconImage src={LidarrIcon} />
  Add Lidarr
</button>
```

#### 3b. Enforce Prefix During Rename

**Change**: Update `SectionNameField` to accept an `expectedPrefix` prop and enforce it during rename.

**Updated Interface**:
```typescript
interface SectionNameFieldProps {
  label: string;
  currentName: string;
  placeholder?: string;
  tooltip?: string;
  expectedPrefix?: string; // New prop
  onRename: (newName: string) => void;
}
```

**Updated `commit` Function in `SectionNameField`**:
```typescript
const commit = () => {
  const trimmed = value.trim();
  
  if (!trimmed) {
    setValue(currentName);
    return;
  }
  
  let adjustedName = trimmed;
  
  // Enforce prefix if specified
  if (expectedPrefix && !trimmed.startsWith(expectedPrefix)) {
    // If user entered something without the prefix, prepend it
    adjustedName = expectedPrefix + (trimmed.startsWith("-") ? trimmed : `-${trimmed}`);
  }
  
  if (adjustedName !== currentName) {
    onRename(adjustedName);
  } else {
    setValue(currentName); // Reset if no actual change
  }
};
```

**Update `ArrInstanceModal` to Pass Prefix**:
```typescript
function ArrInstanceModal({ keyName, state, onChange, onRename, onClose }: ArrInstanceModalProps): JSX.Element {
  // ... existing code ...

  // Determine expected prefix from keyName
  const getExpectedPrefix = (name: string): string | undefined => {
    if (name.startsWith("Radarr")) return "Radarr";
    if (name.startsWith("Sonarr")) return "Sonarr";
    if (name.startsWith("Lidarr")) return "Lidarr";
    return undefined;
  };
  
  const expectedPrefix = getExpectedPrefix(keyName);

  // ... in render ...
  
  // Update SectionNameField usage:
  <SectionNameField
    label="Instance Name"
    currentName={keyName}
    placeholder="Enter instance name"
    onRename={(newName) => onRename(keyName, newName)}
    expectedPrefix={expectedPrefix}
  />
}
```

**Behavior**:
- User adds a Radarr instance → auto-generates "Radarr-1"
- Modal opens, user can rename to "Radarr-Movies" (prefix enforced)
- If user tries to rename to "Movies", it becomes "Radarr-Movies"
- If user tries to rename to "Sonarr-Movies" from a Radarr instance, it becomes "Radarr-Sonarr-Movies" (prevents type changes)
- Suffix is fully customizable

## Implementation Checklist

### Phase 0: Comprehensive Review
- [ ] Fix 0: Audit all field paths against `gen_config.py` and actual config structure
- [ ] Fix 0: Review all validation functions for completeness
- [ ] Fix 0: Test loading logic with various config states (empty, partial, complete)
- [ ] Fix 0: Verify saving logic preserves structure and handles all data types
- [ ] Fix 0: Document any additional issues found during review

### Phase 1: Seeding Field Fix
- [ ] Fix 1: Update seeding field paths in `ARR_SEEDING_FIELDS`
- [ ] Fix 1: Verify loading and saving works correctly with updated paths
- [ ] Test: Verify seeding settings load from existing configs
- [ ] Test: Verify seeding settings are editable and save correctly

### Phase 2: Section Visibility
- [ ] Fix 2: Verify all section `defaultOpen` states in `ArrInstanceModal`
- [ ] Fix 2: Ensure consistency across all modals
- [ ] Test: Verify sections expand/collapse correctly

### Phase 3: Naming Conventions
- [ ] Fix 3a: Implement `generateArrName()` helper function
- [ ] Fix 3a: Update `handleAddArr()` to use type-based generation
- [ ] Fix 3a: Update UI buttons to pass type instead of fixed names
- [ ] Fix 3b: Add `expectedPrefix` prop to `SectionNameFieldProps`
- [ ] Fix 3b: Update `commit()` logic in `SectionNameField`
- [ ] Fix 3b: Update `ArrInstanceModal` to determine and pass prefix
- [ ] Test: Verify adding Radarr generates "Radarr-1", "Radarr-2", etc.
- [ ] Test: Verify renaming enforces prefix (e.g., "Movies" → "Radarr-Movies")
- [ ] Test: Verify renaming allows suffix customization

### Phase 4: Integration Testing
- [ ] Test: All Settings fields load/save correctly
- [ ] Test: All WebUI fields work correctly
- [ ] Test: All qBit fields work correctly
- [ ] Test: All Arr instance fields across all sections work
- [ ] Test: Quality Profile Mappings work correctly
- [ ] Test: Tracker add/edit/delete works correctly
- [ ] Test: Ombi/Overseerr integration fields work
- [ ] Test: Protected keys cannot be modified
- [ ] Test: Invalid values trigger validation errors
- [ ] Test: Config reload after save shows updated values

### Phase 5: Build and Container Testing
- [ ] Build: Run WebUI build (`cd webui && npm run build`)
- [ ] Build: Verify no TypeScript compilation errors
- [ ] Build: Run ESLint (`cd webui && npm run lint`)
- [ ] Build: Fix all ESLint errors and warnings
- [ ] Build: Verify WebUI static files are generated correctly
- [ ] Container: Build Docker container using `compose.yml`
- [ ] Container: Start container and verify qBitrr starts correctly
- [ ] Container: Test WebUI is accessible and loads without errors
- [ ] Container: Test all config view functionality in containerized environment
- [ ] Container: Verify config persistence across container restarts
- [ ] Container: Check logs for any runtime errors or warnings
- [ ] Container: Test with real qBittorrent and Arr instances if available
- [ ] Container: Stop and remove container after successful testing

## Testing Scenarios

### Comprehensive Config Logic
1. Load empty config → all defaults populate
2. Load partial config → missing fields use defaults, existing fields load correctly
3. Load complete config → all values display correctly
4. Modify field → change detected, saves correctly
5. Invalid value → validation error shown, save blocked
6. Protected field (ConfigVersion) → cannot be modified
7. Array field (PingURLs, Trackers) → add/remove/edit works
8. Nested object (EntrySearch.Ombi) → all subfields work
9. Number field with -1 (disabled) → accepts and saves
10. Checkbox field → toggles correctly
11. Select field (Theme, ConsoleLevel) → options work
12. Password/secure field → masked correctly, editable

### Seeding Settings
1. Load config with seeding values under `Torrent.FieldName` → values display correctly
2. Edit seeding value → saves to correct location, reloads correctly
3. Set value to -1 (disable) → accepts and saves
4. Set value to valid number → accepts and saves
5. Set value to invalid (e.g., -2) → shows validation error

### Arr Instance Naming
1. Click "Add Radarr" → generates "Radarr-1", opens modal
2. Add second Radarr → generates "Radarr-2"
3. Delete "Radarr-1", add new → generates "Radarr-3" (next available)
4. Rename "Radarr-1" to "Movies" → becomes "Radarr-Movies"
5. Rename "Radarr-1" to "Radarr-Custom" → stays "Radarr-Custom"
6. Rename "Radarr-1" to "" (empty) → reverts to "Radarr-1"
7. Cannot change "Radarr-1" to "Sonarr-1" → becomes "Radarr-Sonarr-1"

### Section Visibility
1. Open Arr instance modal → general fields and Entry Search visible
2. Scroll down → Torrent, Seeding, Trackers sections collapsed
3. Expand Seeding → fields visible and editable
4. Close and reopen modal → sections reset to default state

## Build and Testing Process

Once all code changes are complete, the following build and testing process must be executed before deployment:

### 1. WebUI Build
```bash
cd webui
npm ci                    # Clean install dependencies
npm run lint              # Run ESLint checks
npm run build             # Build production assets
```

**Requirements**:
- No TypeScript compilation errors
- No ESLint errors (warnings should be addressed if possible)
- Build completes successfully and generates static files in `webui/dist/`
- Static files are copied to `qBitrr/static/` for bundling

### 2. Python Backend Checks
```bash
# From project root
make reformat             # Run pre-commit hooks (black, isort, etc.)
# Verify no formatting issues remain
```

### 3. Docker Container Build and Testing
```bash
# Build container using docker-compose
docker-compose build

# Start container in detached mode
docker-compose up -d

# Follow logs to verify startup
docker-compose logs -f qbitrr

# Test WebUI accessibility
curl http://localhost:6969/ui
# Should return HTML without errors

# Access WebUI in browser
# Open http://localhost:6969/ui
# Test all config view functionality:
# - Load existing config
# - Add/edit/delete Arr instances
# - Modify seeding settings
# - Test all field types (numbers, checkboxes, selects, etc.)
# - Save changes and verify persistence
# - Reload config and verify changes are preserved

# Check container logs for errors
docker-compose logs qbitrr | grep -i error

# Stop and remove container after testing
docker-compose down
```

**Container Testing Requirements**:
- Container builds without errors
- qBitrr starts successfully (no crashes or fatal errors)
- WebUI loads and is accessible at http://localhost:6969/ui
- All config view functionality works in containerized environment
- Config changes persist across saves and reloads
- No runtime errors in container logs
- (Optional) Test with real qBittorrent and Arr instances if available

### 4. Pre-Deployment Checklist
- [ ] All code changes committed with clear commit messages
- [ ] WebUI builds successfully with no errors
- [ ] ESLint passes with no errors
- [ ] Pre-commit hooks pass (formatting, linting)
- [ ] Docker container builds successfully
- [ ] Container starts and runs without errors
- [ ] WebUI accessible in container
- [ ] All config view features tested and working
- [ ] No errors in container logs
- [ ] Documentation updated (if needed)

## Notes

- **No Config Migration**: All fixes preserve existing config structure and load values as-is
- **Backward Compatibility**: Updated paths match how configs are actually stored
- **User Experience**: Auto-generation reduces naming errors, prefix enforcement maintains consistency
- **Validation**: Existing validation logic remains unchanged and comprehensive
- **No Breaking Changes**: All other config view functionality continues to work unchanged
- **Testing is Critical**: Container testing is mandatory before deployment to catch any integration issues

## Related Files

- `webui/src/pages/ConfigView.tsx` - Main config view component (all fixes)
- `qBitrr/gen_config.py` - Config generation (reference for correct paths)
- `qBitrr/webui.py` - Backend API endpoints (no changes needed)
- `qBitrr/config.py` - Config loading/saving (no changes needed)

## Future Considerations

- Consider adding visual indicators (e.g., badges) showing Arr type in instance list
- Add tooltips explaining the prefix requirement for Arr instances
- Consider adding a "Duplicate Instance" feature that auto-increments the number
- Add validation at form level to warn if Arr instance names don't follow convention (for manually edited configs)
