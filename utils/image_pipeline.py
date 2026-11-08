
from agents.image_researcher import search_commons_images
from utils.image_downloader import download_image


def add_images_to_blog(
    topic: str,
    blog_content: str,
    max_images: int = 3,
) -> dict:
    """
    Search, download and add attributed images to a blog.
    """

    if not blog_content.strip():
        raise ValueError("Blog content cannot be empty.")

    print("\nSearching for relevant images...")

    try:
        candidates = search_commons_images(
            query=topic,
            limit=min(max(max_images * 2, 1), 10),
        )
    except Exception as error:
        print(f"Image search skipped: {error}")
        return {
            "blog": blog_content,
            "images": [],
            "warning": str(error),
        }

    selected_images = []
    warnings = []

    for candidate in candidates:
        if len(selected_images) >= max_images:
            break

        try:
            result = download_image(candidate)
            selected_images.append(result)
            print(f"Downloaded: {candidate.get('title', 'Image')}")

        except Exception as error:
            warnings.append(str(error))
            print(f"Skipping image: {error}")

    if not selected_images:
        return {
            "blog": blog_content,
            "images": [],
            "warning": "No suitable images could be downloaded.",
        }

    gallery_parts = ["\n\n## Images\n"]

    for image in selected_images:
        attribution = image["attribution"]

        filename = attribution["filename"]
        title = attribution["title"]
        artist = attribution["artist"] or "Creator not specified"
        license_name = attribution["license"]
        license_url = attribution["license_url"]
        description_url = attribution["description_url"]

        relative_path = f"../images/{filename}"

        gallery_parts.append(
            f"""
![{title}]({relative_path})

**{title}** — {artist}.
License: [{license_name}]({license_url}).
[Original image on Wikimedia Commons]({description_url}).
"""
        )

    updated_blog = blog_content.rstrip() + "\n" + "\n".join(gallery_parts)

    return {
        "blog": updated_blog,
        "images": selected_images,
        "warning": "; ".join(warnings) if warnings else None,
    }
