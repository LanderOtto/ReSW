import os


def read_tail(path, max_lines=100, max_chars=20000):
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, errors="replace") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size == 0:
                return ""
            read_size = min(size, max_chars)
            f.seek(size - read_size)
            tail = f.read(read_size)
            lines = tail.splitlines()
            if len(lines) > max_lines:
                lines = lines[-max_lines:]
            return "\n".join(lines)
    except OSError:
        return ""
