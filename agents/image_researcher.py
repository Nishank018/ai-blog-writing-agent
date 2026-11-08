
import json
import re
from html import unescape
from urllib.parse import urlencode
from urllib.request import Request, urlopen


COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value or "")
    return unescape(value).strip()


def get_metadata_value(metadata: dict, key: str) -> str:
    item = metadata.get(key, {})
    return clean_html(item.get("value", "")) if isinstance(item, dict) else ""


def has_acceptable_license(license_name: str) -> bool:
    if license_name in {"CC0", "Public domain"}:
        return True

    return bool(
        re.match(r"^CC BY(?:-SA)?(?:\s|$)", license_name)
    )


def search_commons_images(query: str, limit: int = 5) -> list[dict]:
    if not query.strip():
        raise ValueError("Image search query cannot be empty.")

    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": min(max(limit, 1), 10),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1200,
    }

    url = f"{COMMONS_API}?{urlencode(params)}"

    request = Request(
        url,
        headers={
            "User-Agent": "AIBlogWritingAgent/1.0 (educational project)"
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise RuntimeError(
            f"Wikimedia Commons image search failed: {error}"
        ) from error

    pages = data.get("query", {}).get("pages", {})
    images = []

    for page in pages.values():
        image_info = page.get("imageinfo", [{}])[0]
        metadata = image_info.get("extmetadata", {})

        license_name = get_metadata_value(
            metadata, "LicenseShortName"
        )

        if not has_acceptable_license(license_name):
            continue

        images.append({
            "title": page.get("title", ""),
            "image_url": image_info.get("thumburl", image_info.get("url", "")),
            "description_url": image_info.get("descriptionurl", ""),
            "artist": get_metadata_value(metadata, "Artist"),
            "license": license_name,
            "license_url": get_metadata_value(metadata, "LicenseUrl"),
        })

    return images
