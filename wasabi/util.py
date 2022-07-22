# coding: utf8
from __future__ import unicode_literals, print_function

import os
import sys
import textwrap
import difflib
import itertools


STDOUT_ENCODING = sys.stdout.encoding if hasattr(sys.stdout, "encoding") else None
ENCODING = STDOUT_ENCODING or "ascii"
NO_UTF8 = ENCODING.lower() not in ("utf8", "utf-8")


# Environment variables
ENV_ANSI_DISABLED = "ANSI_COLORS_DISABLED"  # no colors


class MESSAGES(object):
    GOOD = "good"
    FAIL = "fail"
    WARN = "warn"
    INFO = "info"


COLORS = {
    MESSAGES.GOOD: 2,
    MESSAGES.FAIL: 1,
    MESSAGES.WARN: 3,
    MESSAGES.INFO: 4,
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
    "pink": 5,
    "cyan": 6,
    "white": 7,
    "grey": 8,
    "black": 16,
}


ICONS = {
    MESSAGES.GOOD: "\u2714" if not NO_UTF8 else "[+]",
    MESSAGES.FAIL: "\u2718" if not NO_UTF8 else "[x]",
    MESSAGES.WARN: "\u26a0" if not NO_UTF8 else "[!]",
    MESSAGES.INFO: "\u2139" if not NO_UTF8 else "[i]",
}

INSERT_SYMBOL = "+"
DELETE_SYMBOL = "-"


# Python 2 compatibility
IS_PYTHON_2 = sys.version_info[0] == 2

if IS_PYTHON_2:
    basestring_ = basestring  # noqa: F821
    input_ = raw_input  # noqa: F821
    zip_longest = itertools.izip_longest  # noqa: F821
else:
    basestring_ = str
    input_ = input
    zip_longest = itertools.zip_longest


def color(text, fg=None, bg=None, bold=False, underline=False):
    """Color text by applying ANSI escape sequence.

    text (unicode): The text to be formatted.
    fg (unicode / int): Foreground color. String name or 0 - 256 (see COLORS).
    bg (unicode / int): Background color. String name or 0 - 256 (see COLORS).
    bold (bool): Format text in bold.
    underline (bool): Underline text.
    RETURNS (unicode): The formatted text.
    """
    fg = COLORS.get(fg, fg)
    bg = COLORS.get(bg, bg)
    if not any([fg, bg, bold]):
        return text
    styles = []
    if bold:
        styles.append("1")
    if underline:
        styles.append("4")
    if fg:
        styles.append("38;5;{}".format(fg))
    if bg:
        styles.append("48;5;{}".format(bg))
    return "\x1b[{}m{}\x1b[0m".format(";".join(styles), text)


def wrap(text, wrap_max=80, indent=4):
    """Wrap text at given width using textwrap module.

    text (unicode): The text to wrap.
    wrap_max (int): Maximum line width, including indentation. Defaults to 80.
    indent (int): Number of spaces used for indentation. Defaults to 4.
    RETURNS (unicode): The wrapped text with line breaks.
    """
    indent = indent * " "
    wrap_width = wrap_max - len(indent)
    text = to_string(text)
    return textwrap.fill(
        text,
        width=wrap_width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def format_repr(obj, max_len=50, ellipsis="..."):
    """Wrapper around `repr()` to print shortened and formatted string version.

    obj: The object to represent.
    max_len (int): Maximum string length. Longer strings will be cut in the
        middle so only the beginning and end is displayed, separated by ellipsis.
    ellipsis (unicode): Ellipsis character(s), e.g. "...".
    RETURNS (unicode): The formatted representation.
    """
    string = repr(obj)
    if len(string) >= max_len:
        half = int(max_len / 2)
        return "{} {} {}".format(string[:half], ellipsis, string[-half:])
    else:
        return string


def diff_strings(a, b, fg="black", bg=("green", "red"), add_symbols=False):
    """Compare two strings and return a colored diff with red/green background
    for deletion and insertions.

    a (unicode): The first string to diff.
    b (unicode): The second string to diff.
    fg (unicode / int): Foreground color. String name or 0 - 256 (see COLORS).
    bg (tuple): Background colors as (insert, delete) tuple of string name or
        0 - 256 (see COLORS).
    add_symbols (bool): Whether to add symbols before the diff lines. Uses '+'
        for inserts and '-' for deletions. Default is False.
    RETURNS (unicode): The formatted diff.
    """
    a = a.split("\n")
    b = b.split("\n")
    output = []
    matcher = difflib.SequenceMatcher(None, a, b)
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == "equal":
            for item in a[a0:a1]:
                output.append(item)
        if opcode == "insert" or opcode == "replace":
            for item in b[b0:b1]:
                item = "{} {}".format(INSERT_SYMBOL, item) if add_symbols else item
                output.append(color(item, fg=fg, bg=bg[0]))
        if opcode == "delete" or opcode == "replace":
            for item in a[a0:a1]:
                item = "{} {}".format(DELETE_SYMBOL, item) if add_symbols else item
                output.append(color(item, fg=fg, bg=bg[1]))
    return "\n".join(output)


def get_raw_input(description, default=False, indent=4):
    """Get user input from the command line via raw_input / input.

    description (unicode): Text to display before prompt.
    default (unicode or False/None): Default value to display with prompt.
    indent (int): Indentation in spaces.
    RETURNS (unicode): User input.
    """
    additional = " (default: {})".format(default) if default else ""
    prompt = wrap("{}{}: ".format(description, additional), indent=indent)
    user_input = input_(prompt)
    return user_input


def locale_escape(string, errors="replace"):
    """Mangle non-supported characters, for savages with ASCII terminals.

    string (unicode): The string to escape.
    errors (unicode): The str.encode errors setting. Defaults to `"replace"`.
    RETURNS (unicode): The escaped string.
    """
    string = to_string(string)
    string = string.encode(ENCODING, errors).decode("utf8")
    return string


def can_render(string):
    """Check if terminal can render unicode characters, e.g. special loading
    icons. Can be used to display fallbacks for ASCII terminals.

    string (unicode): The string to render.
    RETURNS (bool): Whether the terminal can render the text.
    """
    try:
        string.encode(ENCODING)
        return True
    except UnicodeEncodeError:
        return False


def _windows_console_supports_ansi():
    """Returns True if sys.stdout is pointing to a Windows console, and that console
    supports ANSI escapes.

    Attempts to enable ANSI support if it's not already enabled.
    """
    # Do these imports lazily, because they'll be slow/broken on non-Windows platforms
    import msvcrt
    import ctypes

    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    kernel32.GetConsoleMode.restype = ctypes.c_int

    kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.SetConsoleMode.restype = ctypes.c_int

    def GetConsoleMode(handle):
        flags = ctypes.c_uint(0)
        ok = kernel32.GetConsoleMode(handle, ctypes.byref(flags))
        if not ok:
            raise ctypes.WinError()
        return flags.value

    def SetConsoleMode(handle, flags):
        ok = kernel32.SetConsoleMode(handle, flags)
        if not ok:
            raise ctypes.WinError()

    console = msvcrt.get_osfhandle(sys.stdout.fileno())
    try:
        # Try to enable ANSI output support
        flags = GetConsoleMode(console)
        SetConsoleMode(console, flags | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

        # Check whether it worked
        flags = GetConsoleMode(console)
        if flags & ENABLE_VIRTUAL_TERMINAL_PROCESSING:
            return True
        else:
            return False
    except OSError:
        return False

def supports_ansi():
    """Returns True if the running system's terminal supports ANSI escape sequences for
    color, formatting etc. and False otherwise. Approximate, but good enough.

    RETURNS (bool): Whether the terminal supports ANSI colors.

    """
    if os.getenv(ENV_ANSI_DISABLED):
        return False

    if sys.platform == "win32":
        if "ANSICON" in os.environ:
            return True
        return _windows_console_supports_ansi()

    return True


def to_string(text):
    """Minimal compat helper to make sure text is unicode. Mostly used to
    convert Paths and other Python objects.

    text: The text/object to be converted.
    RETURNS (unicode): The converted string.
    """
    if not isinstance(text, basestring_):
        if IS_PYTHON_2:
            text = str(text).decode("utf8")
        else:
            text = str(text)
    return text
