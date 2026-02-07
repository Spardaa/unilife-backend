"""
Tests for timezone-aware time parsing in agent tools.

These tests verify that:
1. Naive datetime strings (without timezone) are treated as local time (Asia/Shanghai)
2. Timezone-aware datetime strings are preserved correctly
3. The frontend-backend time flow is consistent
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
import pytz

# Import the function to test
import sys
sys.path.insert(0, '/Users/natsu/Desktop/ZeroD/unilife-backend')
from app.agents.tools import parse_time_with_timezone


class TestParseTimeWithTimezone:
    """Test suite for parse_time_with_timezone helper function"""
    
    def test_naive_datetime_gets_localized(self):
        """Naive datetime strings should be localized to Asia/Shanghai"""
        # AI typically generates times like this (no timezone)
        naive_str = "2026-02-07T10:00:00"
        
        result = parse_time_with_timezone(naive_str)
        
        assert result is not None
        assert result.tzinfo is not None
        # Should be 10:00 in Asia/Shanghai
        assert result.hour == 10
        assert result.minute == 0
        # Verify it's Asia/Shanghai timezone
        assert "Asia/Shanghai" in str(result.tzinfo) or "CST" in str(result.tzinfo.tzname(result) or "")
    
    def test_utc_datetime_preserved(self):
        """UTC datetime strings should remain as UTC"""
        utc_str = "2026-02-07T10:00:00+00:00"
        
        result = parse_time_with_timezone(utc_str)
        
        assert result is not None
        assert result.tzinfo is not None
        # The time should be 10:00 UTC (not shifted)
        assert result.hour == 10
    
    def test_timezone_aware_datetime_preserved(self):
        """Datetime with explicit timezone should be preserved"""
        # Already has +08:00 (Asia/Shanghai)
        tz_str = "2026-02-07T10:00:00+08:00"
        
        result = parse_time_with_timezone(tz_str)
        
        assert result is not None
        assert result.tzinfo is not None
        assert result.hour == 10
    
    def test_none_input_returns_none(self):
        """None input should return None"""
        result = parse_time_with_timezone(None)
        assert result is None
    
    def test_empty_string_returns_none(self):
        """Empty string should return None"""
        result = parse_time_with_timezone("")
        assert result is None
    
    def test_invalid_format_returns_none(self):
        """Invalid format should return None (not raise)"""
        result = parse_time_with_timezone("not-a-date")
        assert result is None
    
    def test_date_only_string(self):
        """Date-only string should work (midnight assumed)"""
        date_str = "2026-02-07"
        
        result = parse_time_with_timezone(date_str)
        
        assert result is not None
        assert result.hour == 0
        assert result.minute == 0
    
    def test_custom_timezone(self):
        """Custom timezone parameter should be respected"""
        naive_str = "2026-02-07T15:00:00"
        
        result = parse_time_with_timezone(naive_str, default_tz="America/New_York")
        
        assert result is not None
        # Should be localized to New York timezone
        assert result.hour == 15


class TestTimezoneConsistency:
    """Test that the full flow maintains timezone consistency"""
    
    def test_ai_generated_time_not_shifted(self):
        """
        Simulate AI scenario:
        - AI says "10:00 meeting"
        - AI generates "2026-02-07T10:00:00" (no timezone)
        - Result should display as 10:00 in local timezone, not 18:00 (UTC+8 shift)
        """
        # This is what the AI would generate
        ai_time_str = "2026-02-07T10:00:00"
        
        # Parse with our fixed function
        parsed = parse_time_with_timezone(ai_time_str)
        
        # When formatted for display in Asia/Shanghai, should still be 10:00
        shanghai_tz = pytz.timezone("Asia/Shanghai")
        local_time = parsed.astimezone(shanghai_tz)
        
        assert local_time.hour == 10, \
            f"Expected 10:00 in local time, got {local_time.hour}:00. " \
            f"This indicates an 8-hour timezone shift bug!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
