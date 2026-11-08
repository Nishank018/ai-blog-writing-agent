
import json
import os
import re
import tempfile
from threading import Lock
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MAX_IMAGE_SIZE = 15 * 1024 * 1024  # 15 MB
_manifest_lock = Lock()

ALLOWED_HOSTS = {
    "commons.wikimedia.org",
    "upload.wikimedia.org",
    "thumb.wikimedia.org",
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
    extension = IMAGE_EXTENSIONS[content_type]
    stem = filename[:-len(extension)]
    collision_number = 2
    while True:
        image_path = output_folder / filename
        try:
            with image_path.open("xb") as image_file:
                image_file.write(image_data)
            break
        except FileExistsError:
            filename = f"{stem[:75]}-{collision_number}{extension}"
            collision_number += 1

    attribution = {
        "filename": filename,
        "title": image.get("title", ""),
        "artist": image.get("artist", ""),
        "license": image.get("license", ""),
        "license_url": image.get("license_url", ""),
        "description_url": image.get("description_url", ""),
    }

    manifest_path = output_folder / "image_attributions.json"

    with _manifest_lock:
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, list):
                raise ValueError("Image attribution manifest is invalid.")
        else:
            manifest = []

        manifest.append(attribution)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output_folder,
                prefix=".image-attributions-",
                suffix=".tmp",
                delete=False,
            ) as manifest_file:
                temp_path = Path(manifest_file.name)
                json.dump(manifest, manifest_file, indent=2, ensure_ascii=False)
                manifest_file.flush()
                os.fsync(manifest_file.fileno())
            os.replace(temp_path, manifest_path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    return {
        "path": str(image_path),
        "attribution": attribution,
    }
