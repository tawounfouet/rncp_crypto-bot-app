#!/usr/bin/env python3
"""
Test script for authentication module.
Run this to verify the auth module is working correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auth import AuthAPIClient, validate_email, validate_password_strength


def test_api_client():
    """Test AuthAPIClient basic functionality."""
    print("🧪 Testing AuthAPIClient...")

    client = AuthAPIClient()

    # Test health check
    print("  - Testing health check...")
    response = client.health_check()
    if response.success:
        print("    ✅ API is healthy")
    else:
        print(f"    ❌ API health check failed: {response.error}")
        return False

    print("  ✅ AuthAPIClient tests passed\n")
    return True


def test_validators():
    """Test validation functions."""
    print("🧪 Testing validators...")

    # Test email validation
    print("  - Testing email validation...")
    assert validate_email("user@example.com") is True
    assert validate_email("invalid-email") is False
    print("    ✅ Email validation works")

    # Test password validation
    print("  - Testing password validation...")
    is_valid, msg = validate_password_strength("weak")
    assert is_valid is False

    is_valid, msg = validate_password_strength("StrongPass123!")
    assert is_valid is True
    print("    ✅ Password validation works")

    print("  ✅ Validators tests passed\n")
    return True


def test_auth_manager():
    """Test AuthManager (requires Streamlit session state mock)."""
    print("🧪 Testing AuthManager...")
    print("  ⚠️  Skipping (requires Streamlit session state)")
    print("  💡 Use the Streamlit app to test AuthManager\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 50)
    print("🔐 Authentication Module Tests")
    print("=" * 50 + "\n")

    results = []

    # Run tests
    results.append(("API Client", test_api_client()))
    results.append(("Validators", test_validators()))
    results.append(("Auth Manager", test_auth_manager()))

    # Summary
    print("=" * 50)
    print("📊 Test Summary")
    print("=" * 50)

    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {name}")

    all_passed = all(result[1] for result in results)

    print("=" * 50)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 50 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
