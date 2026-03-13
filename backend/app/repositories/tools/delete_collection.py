"""
Utility to delete a Qdrant collection entirely (all data + the collection itself).

Usage:
    # Delete the default collection
    python src/delete_collection.py

    # Delete a specific collection by name
    python src/delete_collection.py --collection-name my_collection

    # Skip the confirmation prompt
    python src/delete_collection.py --collection-name my_collection --yes
"""

from app.services.utils.logger import Logger
from app.repositories.config import settings
import socket
import ssl
import argparse
from urllib.parse import urlparse

def get_qdrant_creds():
    return settings.QDRANT_URL, settings.QDRANT_API_KEY


def raw_socket_request(url_str, api_key, path, method="DELETE"):
    parsed = urlparse(url_str)
    host = parsed.hostname
    port = parsed.port or 443

    request = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"api-key: {api_key}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode('utf-8')

    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                ssock.sendall(request)
                response = b""
                while True:
                    chunk = ssock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
    except socket.timeout:
        print(f"[!] Connection to Qdrant Cloud timed out. Check your network.")
        return None
    except Exception as e:
        print(f"[!] Network error: {e}")
        return None

    resp_str = response.decode('utf-8')
    body_start = resp_str.find("\r\n\r\n")
    if body_start != -1:
        body = resp_str[body_start + 4:]
        first = body.find("{")
        last = body.rfind("}")
        if first != -1 and last != -1:
            try:
                return json.loads(body[first:last + 1])
            except json.JSONDecodeError:
                pass
    return resp_str


def delete_collection(collection_name=settings.COLLECTION_NAME, skip_confirm=False):
    qdrant_url, qdrant_api = get_qdrant_creds()

    print(f"\nTarget collection: '{collection_name}'")
    print(f"Qdrant endpoint : {qdrant_url}")

    if not skip_confirm:
        confirm = input(f"\nâš   This will permanently delete ALL data in '{collection_name}'. Proceed? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Aborted. No changes were made.")
            return

    print(f"\nDeleting collection '{collection_name}'...")
    result = raw_socket_request(qdrant_url, qdrant_api, path=f"/collections/{collection_name}")

    if result is None:
        print("Failed to contact Qdrant Cloud.")
        return

    if isinstance(result, dict):
        status = result.get("status", "unknown")
        if status == "ok" and result.get("result") is True:
            print(f"âœ“ Collection '{collection_name}' deleted successfully.")
        elif "error" in str(result):
            print(f"âœ— Error: {result['status'].get('error', result)}")
        else:
            print(f"Response: {result}")
    else:
        print(f"Raw response: {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Delete a Qdrant collection and all its data permanently."
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default=settings.COLLECTION_NAME,
        help=f"Name of the Qdrant collection to delete (default: {settings.COLLECTION_NAME})"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt and delete immediately"
    )
    args = parser.parse_args()
    delete_collection(collection_name=args.collection_name, skip_confirm=args.yes)
