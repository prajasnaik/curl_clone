# Basic Curl Clone (Socket Implementation)

A very basic Python script mimicking some functionalities of curl using standard libraries (`socket`, `ssl`, `urllib`).

## Features

*   Send GET requests
*   Send POST requests with data
*   Handles cookies (persistent storage in `cookies.txt`)
*   Handles redirects automatically (by default, use `--no-location` to disable)
*   Verbose mode (`-v`) shows request/response headers and redirect info.
*   Handles basic `gzip` and `deflate` content encoding.

## Installation

1.  Clone or download this script.
```bash
git clone https://github.com/prajasnaik/curl_clone/
```
2.  No external libraries needed (uses only Python standard library).

## Usage

```bash
python basic_curl.py <URL> [options]
```

**Options:**

*   `-X <method>`: Request method (GET/POST). Default: GET.
*   `-d <data>`: POST data (e.g., "key=value&key2=value2").
*   `-L`: Follow redirects (default).
*   `--no-location`: Do not follow redirects.
*   `-v`: Verbose output.
*   `-H` : Manually give a few headers

**Examples:**

*   **GET request:**
    ```bash
    python basic_curl.py https://httpbin.org/get
    ```

*   **POST request with data:**
    ```bash
    python basic_curl.py https://httpbin.org/post -X POST -d "key1=value1&key2=value2"
    ```

*   **Disable redirects:**
    ```bash
    python basic_curl.py https://httpbin.org/redirect/1 --no-location
    ```

*   **Verbose GET request showing headers and potential redirects:**
    ```bash
    python basic_curl.py https://httpbin.org/redirect/2 -v
    ```

*   **Request involving cookies (cookies stored in `cookies.txt`):**
    ```bash
    # First request sets a cookie (check cookies.txt after)
    python basic_curl.py https://httpbin.org/cookies/set/sessioncookie/12345 -v
    # Second request to the same domain should send the cookie back
    python basic_curl.py https://httpbin.org/cookies -v
    ```
