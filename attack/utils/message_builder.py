import base64
import os
from mimetypes import guess_type


def _local_image_to_data_url(image_path: str) -> str:
    mime_type, _ = guess_type(image_path)
    if mime_type is None:
        mime_type = "application/octet-stream"
    with open(image_path, "rb") as image_file:
        base64_encoded_data = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{base64_encoded_data}"


def _normalize_single_image(img):
    if not isinstance(img, str):
        return img
    if img.startswith("http://") or img.startswith("https://") or img.startswith("data:"):
        return img
    if os.path.exists(img):
        return _local_image_to_data_url(img)
    return img


def normalize_images(inputs):
    if not isinstance(inputs, dict):
        return []
    images = inputs.get("images")
    if images is None:
        images = inputs.get("image")
    if images is None:
        images = inputs.get("image_url")
    if images is None:
        image_rel = inputs.get("image_rel")
        if image_rel:
            image_root_in = inputs.get("image_root_in")
            images = os.path.join(image_root_in, image_rel) if image_root_in else image_rel
    if images is None:
        for key in ("source_image_path", "image_path"):
            if inputs.get(key):
                images = inputs.get(key)
                break
    if images is None:
        return []
    if isinstance(images, (list, tuple)):
        return [_normalize_single_image(img) for img in images if img]
    if isinstance(images, str):
        return [_normalize_single_image(images)]
    return []


def build_messages(query, inputs=None, system_prompt=None):
    images = normalize_images(inputs)
    if images:
        content = [{"type": "text", "text": query or ""}]
        for url in images:
            content.append({"type": "image_url", "image_url": {"url": url}})
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})
        return messages

    if system_prompt:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query or ""},
        ]
    return query or ""
