import sys
import argparse
from .cookies import load_cookies_from_file
import json
from .http_client import make_request

def main():
    # Load cookies before doing anything else
    load_cookies_from_file()

    parser = argparse.ArgumentParser(description="Basic curl clone using Python sockets.")
    parser.add_argument("url", help="The URL to request.")
    parser.add_argument("-X", "--request", default="GET", choices=["GET", "POST"],
                        help="Specify request command to use (GET, POST). Default is GET.")
    parser.add_argument("-d", "--data", help="HTTP POST data (e.g., 'key1=value1&key2=value2').")
    parser.add_argument("-L", "--location", action="store_true", default=True, # Default True like curl
                        help="Follow redirects (default). Use --no-location to disable.")
    parser.add_argument("--no-location", action="store_false", dest="location",
                        help="Do not follow HTTP redirects.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Make the operation more talkative, showing request/response headers.")
    parser.add_argument("-H", "--header", action="append", default=[],
                        help="Pass custom header(s) to the server (e.g., 'Header: Value'). Can be specified multiple times.")

    args = parser.parse_args()

    method = args.request.upper()
    url = args.url
    post_data = args.data
    request_headers = args.header

    if method == "POST" and not post_data:
        print("Warning: POST request specified without -d/--data.", file=sys.stderr)
    elif method == "GET" and post_data:
        print("Warning: Data (-d/--data) is ignored for GET requests.", file=sys.stderr)
        post_data = None # Ignore data for GET

    status_line, headers, body = make_request(
        method=method,
        url=url,
        data=post_data,
        allow_redirects=args.location,
        verbose=args.verbose,
        request_headers="\r\n".join(request_headers)
    )

    if status_line:
        # Try to decode body as text, fallback to printing bytes representation
        content_type = headers.get('content-type', '').lower()
        charset = 'utf-8' # Default assumption
        if 'charset=' in content_type:
            charset = content_type.split('charset=')[-1].split(';')[0].strip()

        try:
            # Attempt JSON pretty printing first if applicable
            if 'application/json' in content_type:
                 try:
                     # Decode first, then parse JSON
                     decoded_body = body.decode(charset, errors='replace')
                     print(json.dumps(json.loads(decoded_body), indent=2))
                 except (json.JSONDecodeError, UnicodeDecodeError) as e:
                     print(f"\nWarning: Failed to decode/parse JSON ({e}), printing raw text.", file=sys.stderr)
                     # Fallback to printing text representation
                     print(body.decode(charset, errors='replace'))
            else:
                 # Print as text
                 print(body.decode(charset, errors='replace'))
        except LookupError:
             print(f"\nWarning: Unknown encoding '{charset}', printing raw bytes representation.", file=sys.stderr)
             print(repr(body))
        except Exception as e:
             print(f"\nWarning: Error processing body ({e}), printing raw bytes representation.", file=sys.stderr)
             print(repr(body))

    else:
        sys.exit(1) # Exit with error if request failed