"""Shared presentation of plain-text lesson notes; no instructions are inferred."""
import re


def formatted_lines(lines):
    """Recognize explicit heading/number markers, preserving the actual wording."""
    for line in lines:
        if line.endswith(':') and line.isupper():
            yield 'heading', line, None
            continue
        numbered = re.match(r'^(\d+)[.)]\s*(.+)$', line)
        if numbered:
            yield 'item', numbered.group(2), numbered.group(1) + '.'
        else:
            yield 'item', line, '•'
