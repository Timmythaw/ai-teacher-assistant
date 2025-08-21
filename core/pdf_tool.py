import PyPDF2
import re
import logging

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract raw text from a PDF file using PyPDF2 with error handling.
    Returns cleaned text or empty string if extraction fails.
    """
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)

            if not reader.pages:
                logging.warning(f"⚠️ PDF {file_path} has no pages.")
                return ""

            for i, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    else:
                        logging.warning(f"⚠️ Page {i} in {file_path} has no extractable text.")
                except Exception as e:
                    logging.error(f"❌ Failed to extract text from page {i} of {file_path}: {e}")
                    continue

    except FileNotFoundError:
        logging.error(f"❌ PDF file not found: {file_path}")
        return ""
    except Exception as e:
        logging.error(f"❌ Error reading PDF {file_path}: {e}")
        return ""

    return clean_text(text)

def clean_text(raw_text: str) -> str:
    """
    Clean raw PDF text by removing headers, footers, line breaks,
    and excessive whitespace.
    """
    if not raw_text:
        return ""

    # Remove multiple spaces/newlines
    text = re.sub(r"\s+", " ", raw_text)

    # Remove common artifacts like page numbers (standalone numbers)
    text = re.sub(r"\b\d+\b", "", text)

    # Strip leading/trailing spaces
    text = text.strip()

    return text