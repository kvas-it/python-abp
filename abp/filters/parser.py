# This file is part of Adblock Plus <https://adblockplus.org/>,
# Copyright (C) 2006-2016 Eyeo GmbH
#
# Adblock Plus is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# Adblock Plus is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Adblock Plus.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import re
from collections import namedtuple

__all__ = ['parse_filterlist', 'parse_line', 'ParseError']


class ParseError(Exception):
    """Exception thrown by the parser when it encounters invalid input.

    :param error: Description of the error.
    :param text: The text which was being parsed when an error occurred.
    """

    def __init__(self, error, text):
        Exception.__init__(self, '{} in "{}"'.format(error, text))
        self.text = text
        self.error = error


def _line_type(name, field_names, format_string, **attrs):
    """Define a line type.

    :param name: The name of the line type to define.
    :param field_names: A sequence of field names or one space-separated
        string that contains all field names.
    :param format_string: A format specifier for converting this line type
        back to string representation.
    :param attrs: Additional static attributes that will be set on the
        returned class.
    :returns: Class created with `namedtuple` that has `.type` set to
        lowercased `name` and supports conversion back to string with
        `.to_string()` method.
    """
    lt = namedtuple(name, field_names)
    lt.type = name.lower()
    lt.to_string = lambda self: format_string.format(self)
    for name, value in attrs.items():
        setattr(lt, name, value)
    return lt


Header = _line_type('Header', 'version', '[{.version}]')
EmptyLine = _line_type('EmptyLine', '', '')
Comment = _line_type('Comment', 'text', '! {.text}')
Metadata = _line_type('Metadata', 'key value', '! {0.key}: {0.value}')
Include = _line_type('Include', 'target', '%include {0.target}%')
BlockingFilter = _line_type(
    'BlockingFilter', 'expression is_exception options pattern',
    '{.expression}',
    type='filter', filter_type='blocking'
)
HidingFilter = _line_type(
    'HidingFiler', 'expression is_exception selector domains',
    '{.expression}',
    type='filter', filter_type='hiding'
)


METADATA_REGEXP = re.compile(r'!\s*(\w+)\s*:\s*(.*)')
METADATA_KEYS = {'Homepage', 'Title', 'Expires', 'Checksum', 'Redirect',
                 'Version'}
INCLUDE_REGEXP = re.compile(r'%include\s+(.+)%')
HEADER_REGEXP = re.compile(r'\[(Adblock(?:\s*Plus\s*[\d\.]+?)?)\]', flags=re.I)

BFILTER_OPTIONS_REGEXP = re.compile(
    r'\$(~?[\w\-]+(?:=[^,\s]+)?(?:,~?[\w\-]+(?:=[^,\s]+)?)*)$'
)
HFILTER_REGEXP = re.compile(
    r'^([^\/\*\|\@"!]*?)#(\@)?(?:([\w\-]+|\*)'
    r'((?:\([\w\-]+(?:[$^*]?=[^\(\)"]*)?\))*)|#([^{}]+))$'
)
OLD_ATTRS_REGEXP = re.compile(r'\(([\w\-]+)(?:([$^*]?=)([^\(\)"]*))?\)')


def _parse_comment(text):
    match = METADATA_REGEXP.match(text)
    if match and match.group(1) in METADATA_KEYS:
        return Metadata(match.group(1), match.group(2))
    return Comment(text[1:].strip())


def _parse_header(text):
    match = HEADER_REGEXP.match(text)
    if not match:
        raise ParseError('Malformed header', text)
    return Header(match.group(1))


def _parse_instruction(text):
    match = INCLUDE_REGEXP.match(text)
    if not match:
        raise ParseError('Unrecognized instruction', text)
    return Include(match.group(1))


def _tag_and_rules_to_selector(text, tag, attr_rules):
    # Convert old style hiding filter to a CSS selector. Based on
    # ElemHideBase.fromText in lib/filterClasses.js in adblockpluscore.

    if tag == '*':
        tag = ''

    constraints_list = []
    class_or_id = None

    for match in OLD_ATTRS_REGEXP.finditer(attr_rules):
        if match.group(2):
            constraints_list.append('[{}{}"{}"]'.format(*match.groups()))
        else:
            if class_or_id is None:
                class_or_id = match.group(1)
            else:
                raise ParseError(text, 'Duplicate id in attriute rules')

    constraints = ''.join(constraints_list)

    if class_or_id:
        return '{0}.{1}{2},{0}#{1}{2}'.format(tag, class_or_id, constraints)
    if tag or constraints:
        return tag + constraints
    raise ParseError(text, 'Filter matches everything')


def _parse_hiding_filter(text, match):
    params = {
        'expression': text,
        'domains': list(filter(None, match.group(1).split(','))),
        'is_exception': bool(match.group(2)),
        'selector': match.group(5)
    }
    if not params['selector']:
        params['selector'] = _tag_and_rules_to_selector(text, match.group(3),
                                                        match.group(4))
    return HidingFilter(**params)


def _parse_filter_options(text, options):
    # Based on RegExpFilter.fromText in lib/filterClasses.js
    # in adblockpluscore.
    parsed_options = {}

    for option in options.split(','):
        if '=' in option:
            name, value = option.split('=', 1)
        elif option.startswith('~'):
            name, value = option[1:], False
        else:
            name, value = option, True
        if name in {'domain', 'sitekey'}:
            value = value.split('|')
        parsed_options[name] = value

    return parsed_options


def _parse_blocking_filter(text):
    # Based on RegExpFilter.fromText in lib/filterClasses.js
    # in adblockpluscore.
    params = {'expression': text, 'is_exception': False, 'options': {}}

    if text.startswith('@@'):
        params['is_exception'] = True
        text = text[2:]

    opt_match = BFILTER_OPTIONS_REGEXP.search(text) if '$' in text else None
    if opt_match:
        params['pattern'] = text[:opt_match.start(0)]
        options = opt_match.group(1)
        params['options'] = _parse_filter_options(text, options)
    else:
        params['pattern'] = text

    return BlockingFilter(**params)


def _parse_filter(text):
    match = HFILTER_REGEXP.match(text) if '#' in text else False
    if match:
        return _parse_hiding_filter(text, match)
    return _parse_blocking_filter(text)


def parse_line(line_text):
    """Parse one line of a filter list.

    :param line_text: Line of a filter list (must be a unicode string).
    :returns: Parsed line object (see `line_type`).
    :raises ParseError: If the line can't be successfully parsed.
    """
    content = line_text.strip()

    if content == '':
        line = EmptyLine()
    elif content.startswith('!'):
        line = _parse_comment(content)
    elif content.startswith('%') and content.endswith('%'):
        line = _parse_instruction(content)
    elif content.startswith('[') and content.endswith(']'):
        line = _parse_header(content)
    else:
        line = _parse_filter(content)

    assert line.to_string().replace(' ', '') == content.replace(' ', '')
    return line


def parse_filterlist(lines):
    """Parse filter list from an iterable.

    :param lines: List of strings or file or other iterable.
    :returns: Iterator over parsed lines.
    :raises ParseError: Can be thrown during iteration for invalid lines.
    """
    for line in lines:
        yield parse_line(line)
