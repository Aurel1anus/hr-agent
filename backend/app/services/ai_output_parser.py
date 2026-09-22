from __future__ import annotations

import json
import re
from typing import Any


class AIParseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def parse_json_output(raw: str) -> dict[str, Any]:
    """Parse direct JSON first, then only safe presentation fallbacks."""
    if not raw or not raw.strip():
        raise AIParseError("AI_EMPTY_RESPONSE", "模型未返回内容。")
    text = raw.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict): return value
        raise AIParseError("AI_JSON_PARSE_ERROR", "模型输出不是 JSON 对象。")
    except json.JSONDecodeError:
        pass
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        try:
            value = json.loads(fenced.group(1))
            if isinstance(value, dict): return value
        except json.JSONDecodeError:
            pass
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            if isinstance(value, dict): return value
        except json.JSONDecodeError:
            continue
    if text.rstrip().endswith(("{", "[", ",", ":")) or text.count("{") > text.count("}"):
        raise AIParseError("AI_OUTPUT_TRUNCATED", "模型输出疑似被截断。")
    raise AIParseError("AI_JSON_PARSE_ERROR", "模型返回内容无法解析为 JSON 对象。")
