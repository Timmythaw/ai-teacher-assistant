def remove_extension(filename):
    """Remove file extension from filename"""
    if not filename:
        return filename
    
    # Split by last dot and return everything before it
    if '.' in filename:
        return filename.rsplit('.', 1)[0]
    return filename
