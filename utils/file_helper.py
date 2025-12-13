from pathlib import Path
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'.pdf'}

def allowed_file(filename: str) -> bool:
    """Check if the file has an allowed extension."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file, upload_dir: Path) -> Path:
    """
    Save uploaded file with unique name if file exists
    Returns: Path to saved file
    """
    safe_name = secure_filename(file.filename or "")
    dest = upload_dir / safe_name
    i = 1
    while dest.exists():
        dest = upload_dir / f"{dest.stem}_{i}{dest.suffix}"
        i += 1
    file.save(dest.as_posix())
    return dest