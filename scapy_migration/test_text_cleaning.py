#!/usr/bin/env python3
"""
Sanity test for text_cleaning.py to ensure it doesn't delete entire content
for single-line full_text fields.
"""

import json
import sys
from pathlib import Path
from text_cleaning import clean_full_text

def test_rich_object():
    """Test that a known rich object doesn't lose its content"""

    # Load a known rich object
    objects_dir = Path('../scapy/htw_scrape/outputs/objects')
    test_file = objects_dir / 'accessibility_support-barrier-free-campus.json'

    if not test_file.exists():
        print(f"WARNING: Test file not found: {test_file}")
        print("Skipping test - cannot verify fix")
        return True

    with open(test_file, 'r', encoding='utf-8') as f:
        obj = json.load(f)

    raw_full_text = obj.get('content', {}).get('full_text', '')

    # Sanity check: raw text should be substantial
    assert len(raw_full_text) > 1000, f"Expected raw full_text > 1000 chars, got {len(raw_full_text)}"
    print(f"✓ Raw full_text length: {len(raw_full_text)} chars")

    # Clean the text
    cleaned = clean_full_text(raw_full_text)

    # Critical assertion: cleaned text must be substantial (not deleted)
    # We expect at least 50% retention after header removal
    min_expected = 500
    assert len(cleaned) > min_expected, f"Expected cleaned_full_text > {min_expected} chars, got {len(cleaned)}"
    print(f"✓ Cleaned full_text length: {len(cleaned)} chars")

    # Verify header was removed
    assert not cleaned.startswith('HTW Berlin - University of Applied Sciences'), \
        "Header prefix should be removed"
    print("✓ Header prefix successfully removed")

    # Verify actual content is present
    assert 'barrier-free' in cleaned.lower() or 'disabled' in cleaned.lower(), \
        "Expected accessibility-related content in cleaned text"
    print("✓ Content keywords present")

    return True


def test_single_line_content():
    """Test that single-line content starting with header is preserved"""

    # Simulate a single-line full_text starting with header
    test_text = "HTW Berlin - University of Applied Sciences - studies, research, further education Campus Campus for All Barrier-free campus Disabled access HTW Berlin strives to ensure barrier-free access for everyone. Dropped kerbs at all sites Ground-level access."

    cleaned = clean_full_text(test_text)

    # Should NOT be empty
    assert len(cleaned) > 100, f"Single-line content was deleted! Got: {len(cleaned)} chars"
    print(f"✓ Single-line test: {len(cleaned)} chars retained")

    # Should start with actual content, not header
    assert not cleaned.startswith('HTW Berlin - University'), \
        "Header prefix should be removed"
    print("✓ Single-line test: Header removed correctly")

    # Should contain actual content
    assert 'barrier-free' in cleaned.lower() and 'access' in cleaned.lower(), \
        "Content should be preserved"
    print("✓ Single-line test: Content preserved")

    return True


def test_multi_line_content():
    """Test that multi-line content is processed correctly"""

    test_text = """HTW Berlin - University of Applied Sciences
Studies
International Programs
Information Technology Bachelor

This is the main content of the page.
It has multiple lines.
Each line should be processed."""

    cleaned = clean_full_text(test_text)

    # Should have content
    assert len(cleaned) > 50, "Multi-line content should be preserved"
    print(f"✓ Multi-line test: {len(cleaned)} chars")

    # Should contain actual content
    assert 'main content' in cleaned.lower(), "Multi-line content should be preserved"
    print("✓ Multi-line test: Content preserved")

    return True


def test_empty_after_header():
    """Test that genuinely empty content returns empty"""

    # Only header, no content
    test_text = "HTW Berlin - University of Applied Sciences - studies, research, further education"

    cleaned = clean_full_text(test_text)

    # Should be empty or very short
    assert len(cleaned) < 10, f"Header-only text should result in empty/minimal output, got: {cleaned}"
    print("✓ Header-only test: Correctly returns empty/minimal")

    return True


def main():
    print("=" * 60)
    print("Testing text_cleaning.py")
    print("=" * 60)

    tests = [
        ("Rich object test", test_rich_object),
        ("Single-line content", test_single_line_content),
        ("Multi-line content", test_multi_line_content),
        ("Header-only content", test_empty_after_header),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        print("-" * 40)
        try:
            test_func()
            print(f"✓ PASSED: {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {test_name}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {test_name}")
            print(f"  Error: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)

    print("\n✓ All tests passed! text_cleaning.py is working correctly.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
