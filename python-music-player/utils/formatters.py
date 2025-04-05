# utils/formatters.py

def format_duration_ms(ms: int) -> str:
    """Formats duration in milliseconds to M:SS string."""
    if ms < 0:
        ms = 0
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"