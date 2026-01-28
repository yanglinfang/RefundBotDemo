"""
Tests for rate limiter configuration.
"""

from slowapi import Limiter

from src.limiter import limiter


class TestLimiter:
    """Tests for rate limiter."""

    def test_limiter_is_instance_of_limiter(self):
        """Test that limiter is a Limiter instance."""
        assert isinstance(limiter, Limiter)

    def test_limiter_has_key_func(self):
        """Test that limiter has a key function configured."""
        assert limiter._key_func is not None
