class NEM12ParseError(Exception):
    """Raised when a NEM12 line cannot be interpreted."""

    def __init__(self, line_no: int, raw_line: str, reason: str):
        self.line_no = line_no
        self.raw_line = raw_line
        self.reason = reason
        super().__init__(f"line {line_no}: {reason} ({raw_line.strip()!r})")
