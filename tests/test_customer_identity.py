"""
Tests for customer identity utility functions.
"""

import pytest

from src.utils.customer_identity import is_customer_id, is_email


class TestIsCustomerId:
    """Tests for is_customer_id function."""

    def test_valid_customer_id(self):
        """Test valid customer ID format."""
        assert is_customer_id("CUST-ABC123") is True
        assert is_customer_id("CUST-A") is True
        assert is_customer_id("CUST-123") is True
        assert is_customer_id("CUST-ABC") is True

    def test_valid_customer_id_with_whitespace(self):
        """Test customer ID with leading/trailing whitespace."""
        assert is_customer_id("  CUST-ABC123  ") is True
        assert is_customer_id("\tCUST-123\n") is True

    def test_invalid_customer_id_wrong_prefix(self):
        """Test invalid customer ID with wrong prefix."""
        assert is_customer_id("CUSTOMER-123") is False
        assert is_customer_id("CUS-123") is False
        assert is_customer_id("UST-123") is False

    def test_invalid_customer_id_lowercase(self):
        """Test invalid customer ID with lowercase letters."""
        assert is_customer_id("cust-ABC123") is False
        assert is_customer_id("CUST-abc123") is False

    def test_invalid_customer_id_missing_suffix(self):
        """Test invalid customer ID missing suffix."""
        assert is_customer_id("CUST-") is False

    def test_invalid_customer_id_special_chars(self):
        """Test invalid customer ID with special characters."""
        assert is_customer_id("CUST-ABC_123") is False
        assert is_customer_id("CUST-ABC-123") is False
        assert is_customer_id("CUST-ABC@123") is False

    def test_empty_string(self):
        """Test empty string."""
        assert is_customer_id("") is False

    def test_none_value(self):
        """Test None value."""
        assert is_customer_id(None) is False

    def test_whitespace_only(self):
        """Test whitespace only."""
        assert is_customer_id("   ") is False


class TestIsEmail:
    """Tests for is_email function."""

    def test_valid_email(self):
        """Test valid email addresses."""
        assert is_email("user@example.com") is True
        assert is_email("user.name@example.com") is True
        assert is_email("user+tag@example.com") is True
        assert is_email("user@subdomain.example.com") is True

    def test_valid_email_with_whitespace(self):
        """Test email with leading/trailing whitespace."""
        assert is_email("  user@example.com  ") is True
        assert is_email("\tuser@example.com\n") is True

    def test_invalid_email_no_at(self):
        """Test invalid email without @ symbol."""
        assert is_email("userexample.com") is False

    def test_invalid_email_no_domain(self):
        """Test invalid email without domain."""
        assert is_email("user@") is False
        assert is_email("user@.com") is False

    def test_invalid_email_no_tld(self):
        """Test invalid email without TLD."""
        assert is_email("user@example") is False

    def test_invalid_email_no_local_part(self):
        """Test invalid email without local part."""
        assert is_email("@example.com") is False

    def test_invalid_email_spaces(self):
        """Test invalid email with internal spaces."""
        assert is_email("user name@example.com") is False
        assert is_email("user@exam ple.com") is False

    def test_empty_string(self):
        """Test empty string."""
        assert is_email("") is False

    def test_none_value(self):
        """Test None value."""
        assert is_email(None) is False

    def test_whitespace_only(self):
        """Test whitespace only."""
        assert is_email("   ") is False
