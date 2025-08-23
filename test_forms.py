#!/usr/bin/env python3
"""
Test script for Google Forms functionality.
Run this to test the form fetching without starting the Flask app.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from integrations.form_response import get_form_full_info
from integrations.form_render import render_responses_csv_string
from integrations.form_utils import extract_form_id

def test_extract_form_id():
    """Test the form ID extraction function."""
    print("Testing form ID extraction...")
    
    # Test cases
    test_cases = [
        ("https://forms.google.com/forms/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptLL74jvcn0V3dK4/edit", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptLL74jvcn0V3dK4"),
        ("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptLL74jvcn0V3dK4", "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptLL74jvcn0V3dK4"),
        ("https://forms.google.com/forms/d/abc123/edit", "abc123"),
        ("invalid_link", None),
        ("", None),
    ]
    
    for test_input, expected in test_cases:
        result = extract_form_id(test_input)
        status = "✓" if result == expected else "✗"
        print(f"  {status} Input: '{test_input}' -> Expected: '{expected}', Got: '{result}'")
    
    print()

def test_form_fetching():
    """Test the form fetching functionality."""
    print("Testing form fetching...")
    print("Note: This requires valid Google credentials and a real form ID.")
    print()
    
    # You can replace this with a real form ID for testing
    test_form_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptLL74jvcn0V3dK4"
    
    print(f"Attempting to fetch form: {test_form_id}")
    print("(Make sure you have valid credentials.json and token.pickle files)")
    print()
    
    try:
        result = get_form_full_info(test_form_id)
        
        if result["ok"]:
            print("✓ Form fetched successfully!")
            print(f"  Title: {result['form_title']}")
            print(f"  Questions: {result['num_questions']}")
            print(f"  Responses: {result['num_responses']}")
            # Build CSV explicitly for preview
            service_ok = True
            try:
                from core.google_client import get_google_service
                from integrations.forms_fetch import fetch_form_structure, fetch_all_responses
                service = get_google_service("forms", "v1")
                form = fetch_form_structure(service, result['form_id'])
                responses = fetch_all_responses(service, result['form_id'])
                csv_str = render_responses_csv_string(form, responses)
            except Exception:
                service_ok = False
                csv_str = ""

            if service_ok and csv_str:
                print(f"  CSV Size: {len(csv_str)} characters")
                # Show first few lines of CSV
                csv_lines = csv_str.split('\n')[:5]
            else:
                print("  CSV not generated (service unavailable or no responses)")
                csv_lines = []
            print(f"  CSV Preview (first 5 lines):")
            for line in csv_lines:
                print(f"    {line}")
        else:
            print(f"✗ Failed to fetch form: {result['error']}")
            
    except Exception as e:
        print(f"✗ Exception occurred: {e}")
        print("  This might be due to missing credentials or authentication issues.")
    
    print()

def main():
    """Run all tests."""
    print("=" * 60)
    print("Google Forms Functionality Test")
    print("=" * 60)
    print()
    
    test_extract_form_id()
    test_form_fetching()
    
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
