"""
Alibaba Cloud OSS client wrapper.

Uploads avatar PNGs to OSS and returns signed (or public) URLs.
Falls back to local file URLs when OSS credentials are not configured.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _oss_configured() -> bool:
    return bool(
        os.environ.get("ALIBABA_ACCESS_KEY_ID")
        and os.environ.get("ALIBABA_ACCESS_KEY_SECRET")
        and os.environ.get("OSS_BUCKET_NAME")
    )


def upload_file(local_path: str, object_key: str) -> str:
    """
    Upload a local file to OSS and return a URL.
    If OSS is not configured, returns a local file:// URL (dev mode).
    """
    if not _oss_configured():
        return f"file://{Path(local_path).as_posix()}"

    import oss2

    auth = oss2.Auth(
        os.environ["ALIBABA_ACCESS_KEY_ID"],
        os.environ["ALIBABA_ACCESS_KEY_SECRET"],
    )
    endpoint = os.environ.get("OSS_ENDPOINT", "https://oss-ap-southeast-1.aliyuncs.com")
    bucket_name = os.environ["OSS_BUCKET_NAME"]
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    with open(local_path, "rb") as f:
        bucket.put_object(object_key, f)

    # Return public URL (assumes bucket has public-read policy for media)
    region = endpoint.replace("https://", "").replace("http://", "")
    return f"https://{bucket_name}.{region}/{object_key}"


def generate_signed_url(object_key: str, expires: int = 3600) -> Optional[str]:
    """Generate a time-limited signed URL for a private object."""
    if not _oss_configured():
        return None

    import oss2

    auth = oss2.Auth(
        os.environ["ALIBABA_ACCESS_KEY_ID"],
        os.environ["ALIBABA_ACCESS_KEY_SECRET"],
    )
    endpoint = os.environ.get("OSS_ENDPOINT", "https://oss-ap-southeast-1.aliyuncs.com")
    bucket_name = os.environ["OSS_BUCKET_NAME"]
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    return bucket.sign_url("GET", object_key, expires)
