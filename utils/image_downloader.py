
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MAX_IMAGE_SIZE = 15 * 1024 * 1024  # 15 MB

ALLOWED_HOSTS = {
    "commons.wikimedia.org",
    "upload.wikimedia.org",
}

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def make_filename(title: str, extension: str, folder: Path) -> str:
    name = title.replace("File:", "")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()

    if not slug:
        slug = "commons-image"

    filename = f"{slug[:80]}{extension}"
    counter = 2

    while (folder / filename).exists():
        filename = f"{slug[:75]}-{counter}{extension}"
        counter += 1

    return filename


def download_image(image: dict) -> dict:
    image_url = image.get("image_url", "")

    parsed_url = urlparse(image_url)

    if parsed_url.scheme != "https" or parsed_url.hostname not in ALLOWED_HOSTS:
        raise ValueError("Image URL must be an HTTPS Wikimedia Commons URL.")

    request = Request(
        image_url,
        headers={
            "User-Agent": "AIBlogWritingAgent/1.0 (educational project)"
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            final_url = urlparse(response.geturl())

            if (
                final_url.scheme != "https"
                or final_url.hostname not in ALLOWED_HOSTS
            ):
                raise ValueError("Image redirected to an untrusted host.")

            content_type = response.headers.get(
                "Content-Type", ""
            ).split(";")[0].lower()

            if content_type not in IMAGE_EXTENSIONS:
                raise ValueError(
                    f"Unsupported image content type: {content_type}"
                )

            image_data = response.read(MAX_IMAGE_SIZE + 1)

    except Exception as error:
        raise RuntimeError(f"Image download failed: {error}") from error

    if len(image_data) > MAX_IMAGE_SIZE:
        raise ValueError("Image exceeds the 15 MB download limit.")

    project_root = Path(__file__).resolve().parent.parent
    output_folder = project_root / "output" / "images"
    output_folder.mkdir(parents=True, exist_ok=True)

    filename = make_filename(
        image.get("title", "commons-image"),
        IMAGE_EXTENSIONS[content_type],
        output_folder,
    )

    image_path = output_folder / filename
    image_path.write_bytes(image_data)

    attribution = {
        "filename": filename,
        "title": image.get("title", ""),
        "artist": image.get("artist", ""),
        "license": image.get("license", ""),
        "license_url": image.get("license_url", ""),
        "description_url": image.get("description_url", ""),
    }

    manifest_path = output_folder / "image_attributions.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = []

    manifest.append(attribution)

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "path": str(image_path),
        "attribution": attribution,
    }
