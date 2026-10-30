"""Tests for Indian currency formatting."""
import pytest

from app.core.replan import Replanner


def test_format_lakhs():
    """Test formatting in lakhs."""
    replanner = Replanner()
    
    # 25 lakhs
    assert "25.00 lakh" in replanner._format_indian_currency(2500000)
    
    # 2.7 lakhs
    assert "2.70 lakh" in replanner._format_indian_currency(270000)


def test_format_crores():
    """Test formatting in crores."""
    replanner = Replanner()
    
    # 4.85 crores
    result = replanner._format_indian_currency(48500000)
    assert "crore" in result
    assert "4.85" in result


def test_format_small_amounts():
    """Test formatting small amounts."""
    replanner = Replanner()
    
    # Less than 1 lakh
    result = replanner._format_indian_currency(50000)
    assert "₹50,000" in result


def test_format_very_small_amounts():
    """Test formatting very small amounts."""
    replanner = Replanner()
    
    # No lakh/crore
    result = replanner._format_indian_currency(500)
    assert "₹500" in result
