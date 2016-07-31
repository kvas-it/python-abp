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

import pytest

from abp.filters import parse_line, parse_filterlist, ParseError
from abp.filters.parser import Comment, Metadata


def test_parse_empty():
    line = parse_line('    ')
    assert line.type == 'emptyline'


def test_parse_filter():
    line = parse_line('||example.com/banner.gif')
    assert line.type == 'filter'
    assert line.expression == '||example.com/banner.gif'


def test_parse_bfilter():
    flt = '||example.com/banner.gif$image,~match-case,domain=abc.com|def.org'
    line = parse_line(flt)
    assert line.type == 'filter'
    assert line.filter_type == 'blocking'
    assert line.expression == flt
    assert not line.is_exception
    assert line.options == {'image': True, 'match-case': False,
                            'domain': ['abc.com', 'def.org']}
    assert line.pattern == '||example.com/banner.gif'


def test_parse_bfilter_exc():
    flt = '@@||example.com/good.gif'
    line = parse_line(flt)
    assert line.type == 'filter'
    assert line.filter_type == 'blocking'
    assert line.expression == flt
    assert line.is_exception
    assert line.options == {}
    assert line.pattern == '||example.com/good.gif'


def test_parse_hfilter():
    """Element hiding filter with a CSS selector."""
    flt = 'abc.com,cdf.com##div#ad1'
    line = parse_line(flt)
    assert line.type == 'filter'
    assert line.filter_type == 'hiding'
    assert line.expression == flt
    assert not line.is_exception
    assert line.domains == ['abc.com', 'cdf.com']
    assert line.selector == 'div#ad1'


def test_parse_hfilter_exc():
    """Element hiding exception."""
    flt = '#@#div#ad1'
    line = parse_line(flt)
    assert line.type == 'filter'
    assert line.filter_type == 'hiding'
    assert line.expression == flt
    assert line.is_exception
    assert line.domains == []
    assert line.selector == 'div#ad1'


def test_parse_hfilter_old():
    """Simplified element hiding filter."""
    flt = 'abc.com#div(foo)(name=bar)(value=baz)'
    line = parse_line(flt)
    assert line.type == 'filter'
    assert line.filter_type == 'hiding'
    assert line.expression == flt
    assert not line.is_exception
    assert line.domains == ['abc.com']
    assert line.selector == ('div.foo[name="bar"][value="baz"],'
                             'div#foo[name="bar"][value="baz"]')


def test_parse_hfilter_old_2id():
    """Simplified element hiding filter with 2 ids."""
    with pytest.raises(ParseError):
        parse_line('abc.com#div(foo)(bar)')


def test_parse_hfilter_empty():
    """Element hiding filter that matches everything."""
    with pytest.raises(ParseError):
        parse_line('abc.com#*')


def test_parse_comment():
    line = parse_line('! Block foo')
    assert line.type == 'comment'
    assert line.text == 'Block foo'


def test_parse_meta():
    line = parse_line('! Homepage  :  http://aaa.com/b')
    assert line.type == 'metadata'
    assert line.key == 'Homepage'
    assert line.value == 'http://aaa.com/b'


def test_parse_nonmeta():
    line = parse_line('! WrongHeader: something')
    assert line.type == 'comment'


def test_parse_instruction():
    line = parse_line('%include foo:bar/baz.txt%')
    assert line.type == 'include'
    assert line.target == 'foo:bar/baz.txt'


def test_parse_bad_instruction():
    with pytest.raises(ParseError):
        parse_line('%foo bar%')


def test_parse_header():
    line = parse_line('[Adblock Plus 1.1]')
    assert line.type == 'header'
    assert line.version == 'Adblock Plus 1.1'


def test_parse_bad_header():
    with pytest.raises(ParseError):
        parse_line('[Adblock 1.1]')


def test_parse_filterlist():
    result = parse_filterlist(['! foo', '! Title: bar'])
    assert list(result) == [Comment('foo'), Metadata('Title', 'bar')]


def test_exception_timing():
    result = parse_filterlist(['! good line', '%bad line%'])
    assert next(result) == Comment('good line')
    with pytest.raises(ParseError):
        next(result)
