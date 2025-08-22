# tools/email_writer.py
from __future__ import annotations
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from typing import Dict, Any
from core.ai_client import chat_completion
from core.logger import logger


def parse_prompt_to_fields(prompt: str) -> Dict[str, str]:
    """
    Parse user prompt to extract email fields using AI.
    
    Args:
        prompt: User's email instruction
        
    Returns:
        Dict with keys: to_email, to_name, tone, cc, bcc, action, subject_override, notes
        
    Raises:
        Exception: If AI parsing fails
    """
    try:
        logger.debug("Parsing email prompt: %s", prompt[:100] + "..." if len(prompt) > 100 else prompt)
        
        system_prompt = (
            "Extract email-send intent from a single user instruction. "
            "Return compact JSON with keys: to_email, to_name, tone, cc, bcc, action, subject_override, notes. "
            "cc/bcc must be comma-separated strings or empty. "
            "If an item is missing, set it to an empty string. DO NOT invent emails."
        )

        response = chat_completion(
            model="openai/gpt-5-chat-latest",
            messages=[
                {"role": "system", "content": system_prompt}, 
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        try:
            data = json.loads(response)
            logger.debug("AI parsing successful: %s", data)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON: %s", e)
            raise ValueError(f"AI response parsing failed: {e}")

        # Fallback: regex email extraction if AI missed it
        if not data.get("to_email"):
            logger.warning("AI did not extract email, attempting regex fallback")
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", prompt)
            if email_match:
                data["to_email"] = email_match.group(0)
                logger.info("Email extracted via regex: %s", data["to_email"])
            else:
                logger.warning("No email found in prompt via AI or regex")

        # Normalize and validate data
        data["action"] = (data.get("action") or "send").lower()
        data["tone"] = data.get("tone") or "professional, friendly"
        
        # Ensure all fields are strings
        for key in ("cc", "bcc", "to_name", "subject_override", "notes"):
            data[key] = (data.get(key) or "").strip()
            
        logger.info("Email fields parsed successfully: %s", list(data.keys()))
        return data
        
    except Exception as e:
        logger.error("Failed to parse email prompt: %s", e, exc_info=True)
        raise RuntimeError(f"Email prompt parsing failed: {e}")


def draft_email(to_name: str, instruction: str, tone: str = "professional, friendly") -> Dict[str, str]:
    """
    Generate email content using AI.
    
    Args:
        to_name: Recipient's name
        instruction: Email purpose/instruction
        tone: Desired tone for the email
        
    Returns:
        Dict with keys: subject, plain, html
        
    Raises:
        Exception: If AI content generation fails
    """
    try:
        logger.debug("Drafting email for %s with instruction: %s", to_name, instruction[:100] + "..." if len(instruction) > 100 else instruction)
        
        system_prompt = (
            "You write concise, polite emails. "
            "Return JSON with keys: subject, plain, html. "
            "Keep emails professional and to the point."
        )
        
        user_prompt = f"""
Recipient name: {to_name or 'there'}
Instruction / purpose: {instruction}
Tone: {tone}
Length: 120-180 words. Avoid flowery language.
"""
        
        response = chat_completion(
            model="openai/gpt-5-chat-latest",
            messages=[
                {"role": "system", "content": system_prompt}, 
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4
        )
        
        try:
            data = json.loads(response)
            logger.debug("AI email drafting successful")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI email response as JSON: %s", e)
            raise ValueError(f"AI email response parsing failed: {e}")

        # Ensure all required fields are present with fallbacks
        result = {
            "subject": data.get("subject", "Hello"),
            "plain": data.get("plain") or data.get("body", ""),
            "html": data.get("html", ""),
        }
        
        # Validate content
        if not result["plain"].strip():
            logger.warning("AI generated empty plain text, using fallback")
            result["plain"] = f"Hello {to_name or 'there'},\n\n{instruction}\n\nBest regards"
            
        if not result["subject"].strip():
            logger.warning("AI generated empty subject, using fallback")
            result["subject"] = "Message from AI Teacher Assistant"
            
        logger.info("Email content drafted successfully with subject: %s", result["subject"])
        return result
        
    except Exception as e:
        logger.error("Failed to draft email: %s", e, exc_info=True)
        raise RuntimeError(f"Email drafting failed: {e}")


# Test code - only run if this file is executed directly
if __name__ == "__main__":
    try:
        # Test parsing
        test_prompt = "Send an email to john@example.com about the meeting tomorrow"
        parsed = parse_prompt_to_fields(test_prompt)
        print("Parsed fields:", parsed)
        
        # Test drafting
        drafted = draft_email("John", "Reminder about tomorrow's meeting at 2 PM")
        print("Drafted email:", drafted)
        
    except Exception as e:
        print(f"Error testing email writer: {e}")