import socket

def get_ip_address(target_host: str = "google.com", target_port: int = 80) -> str:
    """Return the local IP address used to reach the given target.
    If the connection fails, fall back to 127.0.0.1.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((target_host, target_port))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(("google.com", 80))  # ✓ works on most networks
            return s.getsockname()[0]
    except Exception:
        # Fallback if offline or restricted
        return "127.0.0.1"


def get_ip_address_docker() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"

