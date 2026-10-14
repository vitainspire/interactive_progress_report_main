def fmt_num(v) -> str:
    """Whole-number floats print without a trailing ".0" (30.0 -> "30"),
    matching how the browser-based original tool displayed plain numbers."""
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return f"{v:g}"
    return str(v)
