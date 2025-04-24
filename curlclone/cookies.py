import os
import sys

COOKIE_FILE = "cookies.txt"

# Simple in-memory cookie storage {domain: {path: {name: value}}}
# More robust implementation would handle expires, secure, HttpOnly etc.
cookie_jar = {}

def load_cookies_from_file():
    """Loads cookies from the COOKIE_FILE into the global cookie_jar."""
    global cookie_jar
    cookie_jar = {}
    if not os.path.exists(COOKIE_FILE):
        return
    try:
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): # Ignore empty lines and comments
                    continue
                try:
                    domain, name, value = line.split('\t', 2)
                    if domain not in cookie_jar:
                        cookie_jar[domain] = {}
                    cookie_jar[domain][name] = value
                except ValueError:
                    print(f"Warning: Skipping malformed line in {COOKIE_FILE}: {line}", file=sys.stderr)
    except IOError as e:
        print(f"Warning: Could not read cookie file {COOKIE_FILE}: {e}", file=sys.stderr)

def save_cookies_to_file():
    """Saves the global cookie_jar to the COOKIE_FILE."""
    try:
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            f.write("# Basic Curl Clone Cookies\n")
            f.write("# Format: Domain\tName\tValue\n")
            for domain, names in cookie_jar.items():
                for name, value in names.items():
                    f.write(f"{domain}\t{name}\t{value}\n")
    except IOError as e:
        print(f"Warning: Could not write cookie file {COOKIE_FILE}: {e}", file=sys.stderr)

def get_cookies_for_url(host, path):
    """Retrieves applicable cookies from the jar for a given host and path."""
    cookies_to_send = {}
    for domain, names in cookie_jar.items():
        # Simple domain matching (needs improvement for subdomains)
        if host.endswith(domain):
            cookies_to_send.update(names)
    return '; '.join([f"{name}={value}" for name, value in cookies_to_send.items()])

def store_cookies(set_cookie_headers, default_domain):
    """Parses Set-Cookie headers, stores them in the jar, and saves to file."""
    if not isinstance(set_cookie_headers, list):
        set_cookie_headers = [set_cookie_headers]

    for header_value in set_cookie_headers:
        parts = header_value.split(';')
        name_value = parts[0].strip()
        if '=' not in name_value:
            continue
        name, value = name_value.split('=', 1)
        name = name.strip()
        value = value.strip()

        # Basic parsing for Domain and Path attributes
        domain = default_domain
        for part in parts[1:]:
            part = part.strip()
            if part.lower().startswith('domain='):
                domain = part.split('=', 1)[1].strip()
                # Remove leading dot if present (RFC 6265)
                if domain.startswith('.'):
                    domain = domain[1:]
        if domain not in cookie_jar:
            cookie_jar[domain] = {}
        cookie_jar[domain][name] = value

    # Save the updated jar to the file
    save_cookies_to_file()