import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any
from core.logger import logger
from integrations.email_writer import parse_prompt_to_fields, draft_email
from integrations.gmail_tool import (
    get_gmail_service,
    get_sender_address,
    create_message,
    send_message,
    create_draft,
)


class EmailAgent:
    """
    Agent for composing and sending emails using AI assistance.
    Follows the project's agent pattern with proper error handling and logging.
    """

    llama_model = os.getenv("LLAMA_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    def __init__(self, model=llama_model):
        self.model = model
        self.service = None
        self.sender = None
        self._initialize_gmail_service()

    def _initialize_gmail_service(self):
        """Initialize Gmail service with error handling."""
        try:
            # Use default paths from the project structure
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            credentials_path = os.path.join(project_root, "credentials.json")
            token_path = os.path.join(project_root, "token.json")
            
            logger.info("Initializing Gmail service with credentials: %s", credentials_path)
            self.service = get_gmail_service(
                client_secret_path=credentials_path,
                token_path=token_path
            )
            self.sender = get_sender_address(self.service)
            logger.info("Gmail service initialized successfully. Sender: %s", self.sender)
            
        except FileNotFoundError as e:
            logger.error("Gmail credentials not found: %s", e)
            raise FileNotFoundError(f"Gmail credentials not found. Please ensure credentials.json exists in project root: {e}")
        except Exception as e:
            logger.error("Failed to initialize Gmail service: %s", e, exc_info=True)
            raise RuntimeError(f"Failed to initialize Gmail service: {e}")

    def run(self, prompt: str, *, default_use_html: bool = True) -> Dict[str, Any]:
        """
        Main method to process email prompt and send/draft email.
        
        Args:
            prompt: User's email instruction
            default_use_html: Whether to use HTML formatting by default
            
        Returns:
            Dict with operation result and details
        """
        try:
            logger.info("EmailAgent started with prompt: %s", prompt[:100] + "..." if len(prompt) > 100 else prompt)
            
            # Parse the prompt to extract email fields
            parsed = parse_prompt_to_fields(prompt)
            logger.debug("Parsed email fields: %s", parsed)

            # Validate recipient email
            to_email = (parsed.get("to_email") or "").strip()
            if not to_email:
                logger.warning("No recipient email found in prompt")
                return {
                    "ok": False, 
                    "error": "No recipient email found in the prompt.", 
                    "parsed": parsed
                }

            # Generate email content using AI
            instruction = parsed.get("notes") or prompt
            drafted = draft_email(
                parsed.get("to_name", ""), 
                instruction, 
                parsed.get("tone", "professional, friendly")
            )
            logger.info("Email content drafted successfully")

            # Prepare message parameters
            subject = parsed.get("subject_override") or drafted["subject"]
            body_html = drafted["html"] if (default_use_html and drafted["html"]) else None
            body_text = drafted["plain"]
            cc = parsed.get("cc") or None
            bcc = parsed.get("bcc") or None
            action = parsed.get("action", "send")
            
            # Validate action
            if action not in ("send", "draft"):
                logger.warning("Invalid action '%s', defaulting to 'send'", action)
                action = "send"

            # Create the email message
            msg = create_message(
                to=to_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                cc=cc,
                bcc=bcc,
                attachments=None,
                sender=self.sender,
            )
            logger.debug("Email message created successfully")

            # Execute the requested action
            if action == "draft":
                result = self._create_draft(msg, to_email, subject, body_text)
            else:
                result = self._send_message(msg, to_email, subject, body_text)

            logger.info("Email operation completed successfully: %s", action)
            return result

        except Exception as e:
            logger.error("EmailAgent failed: %s", e, exc_info=True)
            return {"ok": False, "error": f"EmailAgent failed: {e}"}

    def _create_draft(self, msg: Dict[str, Any], to_email: str, subject: str, body_text: str) -> Dict[str, Any]:
        """Create a draft email."""
        try:
            res = create_draft(self.service, message=msg)
            logger.info("Draft created successfully with ID: %s", res.get("id"))
            return {
                "ok": True,
                "mode": "draft",
                "draft_id": res.get("id"),
                "to": to_email,
                "subject": subject,
                "preview": {"plain": body_text},
            }
        except Exception as e:
            logger.error("Failed to create draft: %s", e)
            raise

    def _send_message(self, msg: Dict[str, Any], to_email: str, subject: str, body_text: str) -> Dict[str, Any]:
        """Send an email."""
        try:
            res = send_message(self.service, message=msg)
            logger.info("Email sent successfully with ID: %s", res.get("id"))
            return {
                "ok": True,
                "mode": "send",
                "message_id": res.get("id"),
                "to": to_email,
                "subject": subject,
                "preview": {"plain": body_text},
            }
        except Exception as e:
            logger.error("Failed to send email: %s", e)
            raise


# # Test code - only run if this file is executed directly
# if __name__ == "__main__":
#     try:
#         agent = EmailAgent()
#         result = agent.run(
#             "Send an email to john@example.com about the upcoming meeting tomorrow at 2 PM. "
#             "Make it professional and include the agenda."
#         )
#         print("\n---Email Agent Results---")
#         print(result)
#     except Exception as e:
#         print(f"Error testing EmailAgent: {e}")