import socket
import urllib
import urllib.parse
import zlib
import sys
import ssl
from .cookies import get_cookies_for_url, store_cookies


def parse_url(
        url: str
    ) -> tuple[str, str, int, str]:

    """Parses URL into components."""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme or 'http'
    host = parsed.netloc
    path = parsed.path or '/'
    if parsed.query:
        path += '?' + parsed.query
    port = parsed.port or (443 if scheme == 'https' else 80)
    # Remove port from host if explicitly specified
    if ':' in host:
        host = host.split(':', 1)[0]
    return scheme, host, port, path

def parse_headers(
        header_block: str
    ) -> tuple[str, dict[str, str]]:

    """Parses raw HTTP header block into status line and a dictionary."""
    headers = {}
    lines = header_block.split('\r\n')
    status_line = lines[0]
    for line in lines[1:]:
        if line:
            key, value = line.split(':', 1)
            headers[key.strip().lower()] = value.strip()
    return status_line, headers


def _build_request_lines(
        method: str, 
        host: str, 
        path: str, 
        data: str, 
        request_headers: dict[str, str], 
        cookie_header: str
    ) -> tuple[list[str], bytes]:

    request_lines = []
    request_lines.append(f"{method} {path} HTTP/1.1")
    request_lines.append(f"Host: {host}")
    request_lines.append("User-Agent: basic-curl-clone-socket/0.1")
    request_lines.append("Accept: */*")
    request_lines.append("Accept-Encoding: gzip, deflate")
    request_lines.append("Connection: close")
    if cookie_header:
        request_lines.append(f"Cookie: {cookie_header}")
    if request_headers:
        request_lines.append(request_headers)
    body_bytes = b''
    if method == "POST" and data:
        body_bytes = data.encode('utf-8')
        request_lines.append("Content-Type: application/x-www-form-urlencoded")
        request_lines.append(f"Content-Length: {len(body_bytes)}")
    request_lines.append("")
    request_lines.append("")
    return request_lines, body_bytes

def _send_request(
        sock: socket.socket, 
        request_bytes: bytes
    ) -> None:

    sock.sendall(request_bytes)

def _receive_response(
        sock: socket.socket
    ) -> bytes:
    response_bytes = b''
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response_bytes += chunk
    return response_bytes

def _parse_response(
        response_bytes: bytes
    ) -> tuple[str, dict[str, str], bytes]:

    header_part, body_part = response_bytes.split(b'\r\n\r\n', 1)
    header_block = header_part.decode('utf-8', errors='ignore')
    status_line, headers = parse_headers(header_block)
    return status_line, headers, body_part

def _handle_compression(
        headers: dict[str, str], 
        body_part: bytes
    ) -> bytes:

    if headers.get('content-encoding') == 'gzip':
        try:
            body_part = zlib.decompress(body_part, 16 + zlib.MAX_WBITS)
        except zlib.error as e:
            print(f"Warning: Error decompressing gzip content: {e}. Falling back to raw content.", file=sys.stderr)
    elif headers.get('content-encoding') == 'deflate':
        try:
            body_part = zlib.decompress(body_part)
        except zlib.error as e:
            try:
                body_part = zlib.decompress(body_part, -zlib.MAX_WBITS)
            except zlib.error as e2:
                print(f"Warning: Error decompressing deflate content: {e} / {e2}. Falling back to raw content.", file=sys.stderr)
    return body_part

def _handle_redirect(
        status_code: int, 
        headers: dict[str, str], 
        current_url: str, 
        method: str, 
        data: str, 
        verbose: bool):
    
    location = headers.get('location')
    if location:
        new_url = urllib.parse.urljoin(current_url, location)
        if verbose:
            print(f"* Redirecting to: {new_url} ({status_code})", file=sys.stderr)
        if status_code == 303 or (status_code in (301, 302) and method == "POST"):
            return new_url, "GET", None
        return new_url, method, data
    else:
        print("Warning: Redirect status code received without Location header.", file=sys.stderr)
        return None, method, data


def make_request(
        method,
        url, 
        data=None, 
        allow_redirects=True, 
        max_redirects=5, 
        verbose=False, 
        request_headers = ""
    ) -> tuple[str | None, dict[str, str] | None, bytes | None]:

    """Makes an HTTP/HTTPS request using sockets."""

    redirect_count = 0
    current_url = url

    while redirect_count <= max_redirects:
        scheme, host, port, path = parse_url(current_url)

        # 1. Create Socket & Connect
        sock = socket.create_connection((host, port), timeout=10)
        context = None
        if scheme == 'https':
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)

        try:
            # 2. Build Request
            cookie_header = get_cookies_for_url(host, path)
            request_lines, body_bytes = _build_request_lines(method, host, path, data, request_headers, cookie_header)
            request_str = "\r\n".join(request_lines)
            request_bytes = request_str.encode('utf-8') + body_bytes

            if verbose:
                print(f"> {request_lines[0]}", file=sys.stderr)
                for line in request_lines[1:-2]:
                    print(f"> {line}", file=sys.stderr)
                if body_bytes:
                    print(">", file=sys.stderr)
                    try:
                        print(f"> {body_bytes.decode('utf-8')}", file=sys.stderr)
                    except UnicodeDecodeError:
                        print(f"> [Binary data ({len(body_bytes)} bytes)]", file=sys.stderr)
                print(">", file=sys.stderr)

            # 3. Send Request
            _send_request(sock, request_bytes)

            # 4. Receive Response
            response_bytes = _receive_response(sock)

            # 5. Parse Response
            status_line, headers, body_part = _parse_response(response_bytes)

            if verbose:
                print(f"< {status_line}", file=sys.stderr)
                for key, value in headers.items():
                    print(f"< {key.capitalize()}: {value}", file=sys.stderr)
                print("<", file=sys.stderr)

            # Handle Cookies
            if 'set-cookie' in headers:
                store_cookies(headers.get('set-cookie'), host)

            # Handle Compression
            body_part = _handle_compression(headers, body_part)

            # Handle Redirects
            status_code = int(status_line.split()[1])
            if status_code in (301, 302, 303, 307, 308) and allow_redirects:
                new_url, new_method, new_data = _handle_redirect(status_code, headers, current_url, method, data, verbose)
                if new_url:
                    redirect_count += 1
                    current_url = new_url
                    method = new_method
                    data = new_data
                    continue
                # else fall through to return current response

            return status_line, headers, body_part

        except socket.timeout:
            print(f"Error: Connection to {host}:{port} timed out.", file=sys.stderr)
            return None, None, None
        except socket.gaierror as e:
            print(f"Error: Could not resolve host: {host} ({e})", file=sys.stderr)
            return None, None, None
        except ConnectionRefusedError:
            print(f"Error: Connection refused by {host}:{port}.", file=sys.stderr)
            return None, None, None
        except ssl.SSLError as e:
            print(f"Error: SSL error connecting to {host}:{port} - {e}", file=sys.stderr)
            return None, None, None
        except Exception as e:
            print(f"Error: An unexpected error occurred - {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return None, None, None
        finally:
            if sock:
                sock.close()

    print(f"Error: Maximum redirects ({max_redirects}) exceeded.", file=sys.stderr)
    return None, None, None