import socket
import urllib
import urllib.parse
import zlib
import sys
import ssl
from .cookies import get_cookies_for_url, store_cookies


def parse_url(url):
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

def parse_headers(header_block):
    """Parses raw HTTP header block into status line and a dictionary."""
    headers = {}
    lines = header_block.split('\r\n')
    status_line = lines[0]
    for line in lines[1:]:
        if line:
            key, value = line.split(':', 1)
            headers[key.strip().lower()] = value.strip()
    return status_line, headers


def make_request(method, url, data=None, allow_redirects=True, max_redirects=5, verbose=False, request_headers = ""):
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
            request_lines = []
            request_lines.append(f"{method} {path} HTTP/1.1")
            request_lines.append(f"Host: {host}")
            request_lines.append("User-Agent: basic-curl-clone-socket/0.1")
            request_lines.append("Accept: */*")
            request_lines.append("Accept-Encoding: gzip, deflate") # Ask for compression
            request_lines.append("Connection: close") # Tell server we'll close after response

            # Add cookies
            cookie_header = get_cookies_for_url(host, path)
            if cookie_header:
                request_lines.append(f"Cookie: {cookie_header}")
            
            print(request_headers)

            if request_headers:
                request_lines.append(request_headers)

            body_bytes = b''
            if method == "POST" and data:
                # Assume data is urlencoded string for simplicity
                body_bytes = data.encode('utf-8')
                request_lines.append("Content-Type: application/x-www-form-urlencoded")
                request_lines.append(f"Content-Length: {len(body_bytes)}")
                

            request_lines.append("") # Blank line before body
            request_lines.append("")
            request_str = "\r\n".join(request_lines)
            request_bytes = request_str.encode('utf-8') + body_bytes

            if verbose:
                print(f"> {request_lines[0]}", file=sys.stderr)
                for line in request_lines[1:-2]: # Print headers
                     print(f"> {line}", file=sys.stderr)
                if body_bytes:
                    print(">", file=sys.stderr)
                    try:
                        print(f"> {body_bytes.decode('utf-8')}", file=sys.stderr)
                    except UnicodeDecodeError:
                         print(f"> [Binary data ({len(body_bytes)} bytes)]", file=sys.stderr)
                print(">", file=sys.stderr)


            # 3. Send Request
            sock.sendall(request_bytes)

            # 4. Receive Response
            response_bytes = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_bytes += chunk

            # 5. Parse Response
            header_part, body_part = response_bytes.split(b'\r\n\r\n', 1)
            header_block = header_part.decode('utf-8', errors='ignore') # Headers are usually ASCII/UTF-8 ish
            status_line, headers = parse_headers(header_block)

            if verbose:
                print(f"< {status_line}", file=sys.stderr)
                for key, value in headers.items():
                    print(f"< {key.capitalize()}: {value}", file=sys.stderr)
                print("<", file=sys.stderr)

            # Handle Cookies
            if 'set-cookie' in headers:
                store_cookies(headers.get('set-cookie'), host) # Might be multiple headers

            # Handle Compression
            if headers.get('content-encoding') == 'gzip':
                try:
                    body_part = zlib.decompress(body_part, 16 + zlib.MAX_WBITS)
                except zlib.error as e:
                    print(f"Warning: Error decompressing gzip content: {e}. Falling back to raw content.", file=sys.stderr)
                    # Do NOT modify body_part, just use as-is
            elif headers.get('content-encoding') == 'deflate':
                try:
                    body_part = zlib.decompress(body_part)
                except zlib.error as e:
                    try:
                        body_part = zlib.decompress(body_part, -zlib.MAX_WBITS)
                    except zlib.error as e2:
                        print(f"Warning: Error decompressing deflate content: {e} / {e2}. Falling back to raw content.", file=sys.stderr)


            # Handle Redirects
            status_code = int(status_line.split()[1])
            if status_code in (301, 302, 303, 307, 308) and allow_redirects:
                location = headers.get('location')
                if location:
                    redirect_count += 1
                    # Resolve relative URLs
                    current_url = urllib.parse.urljoin(current_url, location)
                    if verbose:
                        print(f"* Redirecting to: {current_url} ({status_code})", file=sys.stderr)
                    # Change method to GET for 303, potentially for 301/302 (common practice)
                    if status_code == 303 or (status_code in (301, 302) and method == "POST"):
                         method = "GET"
                         data = None # Clear data for GET redirect
                    # Continue loop
                    continue
                else:
                    print("Warning: Redirect status code received without Location header.", file=sys.stderr)
                    # Fall through to return current response

            # Not a redirect or redirects disabled/exceeded, return response
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
            traceback.print_exc() # Uncomment for debugging
            return None, None, None
        finally:
            # 6. Close Socket
            if sock:
                sock.close()

    # Max redirects exceeded
    print(f"Error: Maximum redirects ({max_redirects}) exceeded.", file=sys.stderr)
    return None, None, None