import json
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
import xmltodict


class UnsupportedContentType(Exception):
    pass


def parse_json(content: str) -> Dict[str, Any]:
    return json.loads(content)


def parse_html(content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extracts useful structure from HTML:
    - title
    - meta tags
    - headings
    - links
    - raw text (optional)
    """
    soup = BeautifulSoup(content, "lxml")

    result: Dict[str, Any] = {
        "type": "html",
        "title": soup.title.string if soup.title else None,
        "meta": {},
        "headings": {
            "h1": [h.get_text(strip=True) for h in soup.find_all("h1")],
            "h2": [h.get_text(strip=True) for h in soup.find_all("h2")],
            "h3": [h.get_text(strip=True) for h in soup.find_all("h3")],
        },
        "links": [
            {
                "text": a.get_text(strip=True),
                "href": a.get("href"),
            }
            for a in soup.find_all("a", href=True)
        ],
        "text_snippet": soup.get_text(separator=" ", strip=True)[:2000],  # avoid huge text
    }

    # meta tags
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property")
        content_val = meta.get("content")
        if name and content_val:
            result["meta"][name] = content_val

    if metadata:
        result["metadata"] = metadata

    return result


def parse_xml(content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Converts XML → nested dict using xmltodict.
    """
    parsed = xmltodict.parse(content)
    result: Dict[str, Any] = {
        "type": "xml",
        "data": parsed
    }
    if metadata:
        result["metadata"] = metadata
    return result


def parse_text(content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Simple text document, optionally with extra metadata.
    """
    result: Dict[str, Any] = {
        "type": "text",
        "text": content,
    }
    if metadata:
        result["metadata"] = metadata
    return result


def parse_multimedia(
    media_type: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    For multimedia-related metadata:
    - captions
    - subtitles
    - EXIF
    - OCR text
    We treat `content` as a text/caption/subtitle body and `metadata` as structured info.
    """
    result: Dict[str, Any] = {
        "type": "multimedia",
        "media_type": media_type,   # "image" | "video" | "audio" | etc.
        "description_or_subtitles": content,
    }
    if metadata:
        result["metadata"] = metadata
    return result


def parse_any(
    content_type: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entry point.

    Supported values for `content_type`:
    - "json"
    - "html"
    - "xml"
    - "text"
    - "image_meta"
    - "video_meta"
    - "audio_meta"
    """
    ct = content_type.lower()

    if ct == "json":
        return parse_json(content)
    elif ct == "html":
        return parse_html(content, metadata)
    elif ct == "xml":
        return parse_xml(content, metadata)
    elif ct == "text":
        return parse_text(content, metadata)
    elif ct in ("image_meta", "video_meta", "audio_meta"):
        media = ct.split("_")[0]  # "image" / "video" / "audio"
        return parse_multimedia(media, content, metadata)
    else:
        raise UnsupportedContentType(f"Unsupported content_type: {content_type}")
