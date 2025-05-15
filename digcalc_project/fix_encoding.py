#!/usr/bin/env python3
"""Encoding fixer for Python files.

This script walks through the project directories and attempts to fix
encoding issues in Python files, particularly removing null bytes.
"""

import codecs
import sys
from pathlib import Path


def fix_file_encoding(file_path: Path) -> bool:
    """Fix encoding issues in a single file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if fixed, False if no changes or error

    """
    # Skip this script itself to avoid interference
    if file_path.name == "fix_encoding.py":
        return False

    try:
        # Read file as binary
        content = file_path.read_bytes()

        # Check for null bytes
        if b"\x00" in content:
            print(f"Fixing null bytes in {file_path}")

            # Remove null bytes
            cleaned_content = content.replace(b"\x00", b"")

            # Try to decode as UTF-8
            try:
                # If we can decode it, convert to string and write as text
                text = cleaned_content.decode("utf-8")
                file_path.write_text(text, encoding="utf-8")
                print("  ✓ File is now valid UTF-8")
                return True
            except UnicodeDecodeError:
                print("  ⚠ Could not decode as UTF-8, attempting UTF-16...")
                try:
                    # Try UTF-16 decoding
                    text = cleaned_content.decode("utf-16", errors="replace")
                    file_path.write_text(text, encoding="utf-8")
                    print("  ✓ Converted from UTF-16 to UTF-8")
                    return True
                except Exception:
                    print("  ⚠ UTF-16 failed, attempting direct binary cleanup...")
                    # Last resort: just remove all non-ASCII and control characters
                    printable_content = bytes("".join(chr(c) if 32 <= c < 127 else " "
                                              for c in cleaned_content), "utf-8")
                    file_path.write_bytes(printable_content)
                    print("  ✓ Sanitized binary content")
                    return True
        else:
            # If no null bytes, verify UTF-8 compatibility
            try:
                file_path.read_text(encoding="utf-8")
                return False  # No changes needed
            except UnicodeDecodeError:
                print(f"Fixing other encoding issues in {file_path}")
                # Read as binary and try to interpret as other encodings
                try:
                    text = content.decode("utf-16", errors="replace")
                    file_path.write_text(text, encoding="utf-8")
                    print("  ✓ Converted from UTF-16 to UTF-8")
                    return True
                except Exception:
                    # Last resort: read with errors replaced
                    content_str = content.decode("utf-8", errors="replace")
                    file_path.write_text(content_str, encoding="utf-8")
                    print("  ✓ Replaced invalid characters")
                    return True
    except Exception as e:
        print(f"Error processing {file_path}: {e!s}")
        return False


def recreate_file(file_path: Path) -> bool:
    """Recreate a problematic file by copying content line by line.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if fixed, False if error

    """
    try:
        print(f"Attempting to recreate {file_path} with clean encoding...")

        # Try to read the file with various encodings
        content = None
        for encoding in ["utf-8", "utf-16", "latin-1", "cp1252"]:
            try:
                with codecs.open(str(file_path), "r", encoding=encoding, errors="replace") as f:
                    content = f.read()
                print(f"  ✓ Successfully read with {encoding} encoding")
                break
            except Exception:
                print(f"  ⚠ Failed to read with {encoding} encoding")

        if content is None:
            print("  ✗ Could not read file with any encoding")
            return False

        # Create a temporary file with the correct content
        temp_path = file_path.with_suffix(".tmp.py")
        with codecs.open(str(temp_path), "w", encoding="utf-8") as f:
            f.write(content)

        # Verify the temp file
        try:
            with codecs.open(str(temp_path), "r", encoding="utf-8") as f:
                temp_content = f.read()
            print("  ✓ Temporary file is valid UTF-8")

            # Replace the original file
            file_path.unlink()
            temp_path.rename(file_path)
            print("  ✓ Successfully recreated file")
            return True
        except Exception as e:
            print(f"  ✗ Failed to verify temp file: {e!s}")
            # Clean up
            if temp_path.exists():
                temp_path.unlink()
            return False
    except Exception as e:
        print(f"Error recreating {file_path}: {e!s}")
        return False


def fix_directory(directory: Path, include_subdirs: bool = True) -> int:
    """Fix encoding issues in all Python files in a directory.
    
    Args:
        directory: Path to directory
        include_subdirs: Whether to process subdirectories
        
    Returns:
        Number of files fixed

    """
    fixed_count = 0

    # Get list of Python files
    if include_subdirs:
        files = list(directory.glob("**/*.py"))
    else:
        files = list(directory.glob("*.py"))

    total_files = len(files)
    print(f"Processing {total_files} Python files in {directory}")

    # Process each file
    for i, file_path in enumerate(files, 1):
        print(f"[{i}/{total_files}] Checking {file_path}")

        # Try basic fix first
        if fix_file_encoding(file_path):
            fixed_count += 1
        else:
            # If file still has issues, try to read it
            try:
                file_path.read_text(encoding="utf-8")
                print("  ✓ File is already valid UTF-8")
            except UnicodeDecodeError:
                print("  ⚠ File still has encoding issues, attempting full recreation")
                if recreate_file(file_path):
                    fixed_count += 1

    print(f"Fixed {fixed_count} files out of {total_files}")
    return fixed_count


def create_init_files(directory: Path) -> int:
    """Create clean __init__.py files in directories.
    
    Args:
        directory: Root directory to start from
        
    Returns:
        Number of files created

    """
    created_count = 0

    # Find all directories recursively
    dirs = [d for d in directory.glob("**/*") if d.is_dir()]
    dirs.append(directory)  # Include the root directory

    # Create __init__.py in each directory if it doesn't exist
    for dir_path in dirs:
        init_file = dir_path / "__init__.py"

        if not init_file.exists():
            # Skip if no Python files in directory
            if not list(dir_path.glob("*.py")):
                continue

            print(f"Creating new __init__.py in {dir_path}")
            with open(init_file, "w", encoding="utf-8") as f:
                f.write('"""Package initialization."""\n')
            created_count += 1
        else:
            # Try to fix existing __init__.py
            try:
                # If we can read it, it's fine
                init_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                print(f"Recreating corrupt __init__.py in {dir_path}")
                init_file.unlink()
                with open(init_file, "w", encoding="utf-8") as f:
                    f.write('"""Package initialization."""\n')
                created_count += 1

    print(f"Created or fixed {created_count} __init__.py files")
    return created_count


def main():
    """Main function."""
    # Get the project root (current directory)
    project_root = Path.cwd()

    # Check if specific directories were provided
    if len(sys.argv) > 1:
        directories = [project_root / dir_name for dir_name in sys.argv[1:]]
    else:
        # Default directories to check
        directories = [
            project_root / "src",
            project_root / "tests",
        ]

    # Process each directory
    total_fixed = 0
    for directory in directories:
        if directory.exists() and directory.is_dir():
            print(f"\nProcessing directory: {directory}")
            fixed = fix_directory(directory)
            total_fixed += fixed

            # If files were fixed, also ensure __init__.py files exist and are valid
            if fixed > 0:
                create_init_files(directory)
        else:
            print(f"Directory not found: {directory}")

    print(f"\nTotal files fixed: {total_fixed}")

    if total_fixed > 0:
        print("\nEncoding issues have been fixed. Please run your tests again.")
    else:
        print("\nNo encoding issues found.")


if __name__ == "__main__":
    main()
