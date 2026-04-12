"""Bot version management module"""
import os
from pathlib import Path

VERSION_FILE = Path(__file__).parent / "VERSION"

def get_current_version():
    """Get the current version from VERSION file"""
    if VERSION_FILE.exists():
        try:
            with open(VERSION_FILE, 'r') as f:
                version_str = f.read().strip()
                # Validate format: major.minor.patch
                parts = version_str.split('.')
                if len(parts) == 3 and all(part.isdigit() for part in parts):
                    return tuple(int(part) for part in parts)
        except:
            pass
    return (1, 0, 0)  # Default fallback

def set_version(major, minor, patch):
    """Set the version in VERSION file"""
    version_str = f"{major}.{minor}.{patch}"
    with open(VERSION_FILE, 'w') as f:
        f.write(version_str)
    return (major, minor, patch)

def increment_version(change_type):
    """
    Increment version based on change type
    - 'major': breaking changes, reset minor/patch to 0
    - 'minor': new features, reset patch to 0
    - 'patch': bug fixes
    """
    current = get_current_version()
    major, minor, patch = current

    if change_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif change_type == 'minor':
        minor += 1
        patch = 0
    elif change_type == 'patch':
        patch += 1
    else:
        raise ValueError("change_type must be 'major', 'minor', or 'patch'")

    return set_version(major, minor, patch)

def get_version_string():
    """Get version as string (e.g., '1.0.0')"""
    major, minor, patch = get_current_version()
    return f"{major}.{minor}.{patch}"

# Initialize version file if it doesn't exist
if not VERSION_FILE.exists():
    set_version(1, 0, 0)