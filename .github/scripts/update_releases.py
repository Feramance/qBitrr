#!/usr/bin/env python3
"""
Update GitHub releases with changelog content.
This script extracts changelog entries and updates corresponding GitHub releases.
"""

import re
import subprocess
import sys


def extract_changelog_entries() -> dict[str, str]:
    """Extract all changelog entries from CHANGELOG.md"""
    with open("CHANGELOG.md") as f:
        content = f.read()

    # Split into sections by version
    version_pattern = r"## (v[\d.]+) \((\d{2}/\d{2}/\d{4})\)\n(.*?)(?=\n---\n\n|\Z)"
    versions = re.finditer(version_pattern, content, re.DOTALL)

    entries = {}
    for match in versions:
        version = match.group(1)
        match.group(2)
        body = match.group(3).strip()

        if body:  # Only include non-empty entries
            entries[version] = body

    return entries


def get_existing_releases() -> list[str]:
    """Get list of existing GitHub releases"""
    result = subprocess.run(
        ["gh", "release", "list", "--limit", "100"], capture_output=True, text=True, check=True
    )

    # Parse the tabular output (format: TAG  TITLE  TYPE  DATE)
    releases = []
    for line in result.stdout.strip().split("\n"):
        if line:
            # First column is the tag name
            tag = line.split("\t")[0].strip()
            if tag:
                releases.append(tag)

    return releases


def update_release(tag: str, body: str, dry_run: bool = False) -> bool:
    """Update a GitHub release with new body content"""
    if dry_run:
        print(f"[DRY RUN] Would update {tag}")
        print(f"Body preview (first 200 chars): {body[:200]}...")
        return True

    try:
        # Update the release body
        subprocess.run(
            ["gh", "release", "edit", tag, "--notes", body],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"✓ Updated release {tag}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to update {tag}: {e.stderr}")
        return False


def main():
    """Main entry point"""
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN MODE ===")

    print("Extracting changelog entries...")
    changelog_entries = extract_changelog_entries()
    print(f"Found {len(changelog_entries)} changelog entries")

    print("\nFetching existing GitHub releases...")
    existing_releases = get_existing_releases()
    print(f"Found {len(existing_releases)} existing releases")

    # Update releases that have changelog entries
    updated = 0
    skipped = 0
    failed = 0

    for version, body in changelog_entries.items():
        if version in existing_releases:
            if update_release(version, body, dry_run=dry_run):
                updated += 1
            else:
                failed += 1
        else:
            print(f"⊘ Skipping {version} (release doesn't exist)")
            skipped += 1

    print(f"\n=== Summary ===")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
