def _normalize_images(inputs):
    if not isinstance(inputs, dict):
        return []
    images = inputs.get("images")
    if images is None:
        images = inputs.get("image")
    if images is None:
        images = inputs.get("image_url")
    if images is None:
        return []
    if isinstance(images, (list, tuple)):
        return [img for img in images if img]
    if isinstance(images, str):
        return [images]
    return []


def build_messages(query, inputs=None, system_prompt=None):
    images = _normalize_images(inputs)
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
