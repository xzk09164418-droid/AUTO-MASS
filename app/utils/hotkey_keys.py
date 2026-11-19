"""全局热键的键名规范化与 Win32 虚拟键码映射。

原先位于已删除的 MaaFW 专项适配器（app/task/MaaFW/tools/core/runner/hotkey.py），
全局热键管理器仍需要它，故原样迁出；与前端 canonicalKeyName 保持同一套规则。
"""

from __future__ import annotations

import re


class HotkeyKeyError(ValueError):
    """快捷键无法映射为 Win32 键码。"""


_ALIASES = {
    "CONTROL": "CTRL",
    "CTL": "CTRL",
    "OPTION": "ALT",
    "COMMAND": "META",
    "CMD": "META",
    "WIN": "META",
    "WINDOWS": "META",
    "SUPER": "META",
    "ESC": "ESCAPE",
    "RETURN": "ENTER",
    "SPACEBAR": "SPACE",
    "ARROWLEFT": "LEFT",
    "ARROWRIGHT": "RIGHT",
    "ARROWUP": "UP",
    "ARROWDOWN": "DOWN",
    "PAGEUP": "PAGEUP",
    "PAGEDOWN": "PAGEDOWN",
    "PGUP": "PAGEUP",
    "PGDN": "PAGEDOWN",
    "DEL": "DELETE",
    "INS": "INSERT",
    "BACKTICK": "GRAVE",
    "BACKQUOTE": "GRAVE",
    "APOSTROPHE": "QUOTE",
    "EQUAL": "EQUALS",
    # 小键盘运算键：主键盘的 `-` 是 MINUS（VK_OEM_MINUS），小键盘的减号另有键码。
    "ADD": "NUMPADADD",
    "SUBTRACT": "NUMPADSUBTRACT",
}


_FUNCTION_KEY_RE = re.compile(r"F([1-9]|1[0-9]|2[0-4])\Z")


_WIN32_KEYS = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "ALT": 0x12,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "PRINTSCREEN": 0x2C,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "META": 0x5B,
    "MULTIPLY": 0x6A,
    "PLUS": 0x6B,
    "DECIMAL": 0x6E,
    "DIVIDE": 0x6F,
    "NUMPADMULTIPLY": 0x6A,
    "NUMPADADD": 0x6B,
    "NUMPADSUBTRACT": 0x6D,
    "NUMPADDECIMAL": 0x6E,
    "NUMPADDIVIDE": 0x6F,
    "NUMLOCK": 0x90,
    "SCROLLLOCK": 0x91,
    "SEMICOLON": 0xBA,
    "EQUALS": 0xBB,
    "COMMA": 0xBC,
    # 主键盘的减号（VK_OEM_MINUS）；0x6D 是小键盘减号 VK_SUBTRACT，见 NUMPADSUBTRACT。
    "MINUS": 0xBD,
    "PERIOD": 0xBE,
    "SLASH": 0xBF,
    "GRAVE": 0xC0,
    "BRACKETLEFT": 0xDB,
    "BACKSLASH": 0xDC,
    "BRACKETRIGHT": 0xDD,
    "QUOTE": 0xDE,
}


# 单个标点字符 → 键名，与前端 maafwHotkey.ts 的 PUNCTUATION_ALIASES 同一张表。
_PUNCTUATION_ALIASES = {
    "-": "MINUS",
    "=": "EQUALS",
    ",": "COMMA",
    ".": "PERIOD",
    "/": "SLASH",
    "\\": "BACKSLASH",
    ";": "SEMICOLON",
    "'": "QUOTE",
    "`": "GRAVE",
    "[": "BRACKETLEFT",
    "]": "BRACKETRIGHT",
}


def _canonical_key(value: str) -> str:
    if value == " ":
        return "SPACE"
    normalized = value.strip()
    # 标点要在去掉 `-` / `_` / 空白之前查（与前端 canonicalKeyName 同一顺序）：
    # 否则单独一个 "-" 会被删成空串，判成格式无效。
    if normalized in _PUNCTUATION_ALIASES:
        return _PUNCTUATION_ALIASES[normalized]

    normalized = re.sub(r"[\s_-]+", "", normalized).upper()
    if (
        normalized.startswith("KEY")
        and len(normalized) == 4
        and normalized[-1].isalpha()
    ):
        normalized = normalized[-1]
    elif (
        normalized.startswith("DIGIT")
        and len(normalized) == 6
        and normalized[-1].isdigit()
    ):
        normalized = normalized[-1]

    return _ALIASES.get(normalized, _PUNCTUATION_ALIASES.get(normalized, normalized))


def _win32_keycode(key: str) -> int:
    if len(key) == 1 and (key.isalpha() or key.isdigit()):
        return ord(key)
    function_match = _FUNCTION_KEY_RE.fullmatch(key)
    if function_match:
        return 0x70 + int(function_match.group(1)) - 1
    if key.startswith("NUMPAD") and key[6:].isdigit():
        number = int(key[6:])
        if 0 <= number <= 9:
            return 0x60 + number
    try:
        return _WIN32_KEYS[key]
    except KeyError as exc:
        raise HotkeyKeyError(f"Win32 不支持快捷键: {key}") from exc
