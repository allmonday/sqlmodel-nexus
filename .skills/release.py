#!/usr/bin/env python3
"""Release version skill implementation."""

import re
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True, capture_output=True):
    """Run a shell command and return the result."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True
    )
    if check and result.returncode != 0:
        print(f"❌ Error executing: {cmd}")
        print(f"   {result.stderr}")
        sys.exit(1)
    return result


def validate_version(version):
    """Validate semantic version format."""
    pattern = r'^\d+\.\d+\.\d+$'
    if not re.match(pattern, version):
        print(f"❌ Invalid version format: {version}")
        print("   Version must follow SemVer (e.g., 0.8.2, 1.0.0)")
        sys.exit(1)
    return True


def check_working_directory():
    """Check if working directory is clean."""
    result = run_command("git status --porcelain")
    if result.stdout.strip():
        print("❌ Working directory is not clean")
        print("   Please commit or stash your changes first")
        print("\nUncommitted changes:")
        print(result.stdout)
        sys.exit(1)


def update_pyproject_version(new_version):
    """Update version in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found")
        sys.exit(1)

    content = pyproject_path.read_text()

    # Update version line
    updated = re.sub(
        r'version\s*=\s*["\']([^"\']+)["\']',
        f'version = "{new_version}"',
        content
    )

    if updated == content:
        print("❌ Failed to update version in pyproject.toml")
        sys.exit(1)

    pyproject_path.write_text(updated)
    print(f"✅ Updated pyproject.toml to version {new_version}")


def run_tests():
    """Run the full test suite."""
    print("\n🧪 Running tests...")
    result = run_command("uv run pytest", check=False)
    if result.returncode != 0:
        print("❌ Tests failed")
        print(result.stdout)
        sys.exit(1)
    print("✅ All tests passed")


def create_commit(version):
    """Create a commit for version bump."""
    run_command("git add pyproject.toml uv.lock")
    run_command('git commit -m "bump ver"')
    result = run_command("git rev-parse --short HEAD")
    commit_hash = result.stdout.strip()
    print(f"✅ Created commit: {commit_hash}")
    return commit_hash


def create_tag(version):
    """Create a git tag."""
    tag_name = f"v{version}"
    result = run_command(f"git tag {tag_name}", check=False)
    if result.returncode != 0:
        if "already exists" in result.stderr:
            print(f"❌ Tag {tag_name} already exists")
            sys.exit(1)
        print(f"❌ Failed to create tag: {result.stderr}")
        sys.exit(1)
    print(f"✅ Created tag: {tag_name}")
    return tag_name


def push_tag(tag_name):
    """Push tag to origin."""
    print(f"\n🚀 Pushing tag {tag_name} to origin...")
    result = run_command(f"git push origin {tag_name}", check=False)
    if result.returncode != 0:
        print("❌ Failed to push tag")
        print(f"   {result.stderr}")
        print("\n💡 Tips:")
        print("   - Check your network connection")
        print("   - Verify you have push permissions")
        print(f"   - Try: git push origin {tag_name}")
        sys.exit(1)
    print(f"✅ Tag {tag_name} pushed to origin")


def get_recent_commits(count=5):
    """Get recent commit messages."""
    result = run_command(f"git log --oneline -{count}")
    return result.stdout.strip().split('\n')


def main():
    if len(sys.argv) < 2:
        print("Usage: release <version>")
        print("Example: release 0.8.2")
        sys.exit(1)

    version = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"📦 Release Version: v{version}")
    print(f"{'='*60}\n")

    # Step 1: Validate version
    validate_version(version)

    # Step 2: Check working directory
    print("🔍 Checking working directory...")
    check_working_directory()
    print("✅ Working directory is clean\n")

    # Step 3: Update version in pyproject.toml
    print(f"📝 Updating version to {version}...")
    update_pyproject_version(version)

    # Step 4: Run tests
    run_tests()

    # Step 5: Create commit
    print("\n📝 Creating commit...")
    commit_hash = create_commit(version)

    # Step 6: Create tag
    print("\n🏷️  Creating tag...")
    tag_name = create_tag(version)

    # Step 7: Push tag
    push_tag(tag_name)

    # Step 8: Show summary
    print(f"\n{'='*60}")
    print("✅ Release completed successfully!")
    print(f"{'='*60}")
    print(f"\n📦 Version: {tag_name}")
    print(f"📝 Commit: {commit_hash}")
    print(f"🏷️  Tag: {tag_name}")
    print(f"🚀 Pushed to: origin/{tag_name}")

    print("\n📋 Recent commits included in this release:")
    for commit in get_recent_commits(3):
        print(f"   {commit}")

    print("\n🎉 Done!")


if __name__ == "__main__":
    main()
