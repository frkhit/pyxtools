# -*- coding:utf-8 -*-
from __future__ import absolute_import

import datetime
import json
import logging
import operator
import os
import re
from itertools import takewhile

import requests
from flask_flatpages.page import Page as OldPage, cached_property, yaml
from werkzeug.utils import import_string

from ..basic_tools import get_md5, SingletonMixin, SqliteCache

logger = logging.getLogger(__name__)


class HtmlCache(SingletonMixin):
    cache_file = "./cache.dat"

    def __init__(self, ):
        self.cache = SqliteCache(self.cache_file)

    @classmethod
    def instance(cls):
        """

        :rtype: HtmlCache
        """
        return super(HtmlCache, cls).instance()

    def get_content_id_and_html(self, md_id):
        """

        :type md_id: str
        :rtype: (str, str)
        """
        result = self.cache.get(md_id)
        if result is None:
            return None, None
        return result[0], result[1]

    def set_content_id_and_html(self, md_id, content_id, html_value):
        self.cache.set(key=md_id, value=(content_id, html_value))


def md2html_by_github(content: str) -> str:
    """ use github api """
    logging.info("requesting github...")
    url = "https://api.github.com/markdown"
    return requests.post(url, data=json.dumps({"text": content, "mode": "markdown"})).text


class Page(OldPage):
    def __init__(self, path, meta, body, html_renderer):
        """

        :type body: str
        :type meta: str
        :type path: str
        """
        super(Page, self).__init__(path, meta, body, html_renderer)

        # date re
        self.date_re = re.compile(r"[\d]{4}/[\d]{2}/[\d]{2}(?=/)")

        # 执行meta方法
        if self.meta:
            pass

    @cached_property
    def html(self):
        """The content of the page, rendered as HTML by the configured
        renderer.
        """
        file_name_id = get_md5(self.path.encode("utf-8"))

        old_content_id, content_html = HtmlCache.instance().get_content_id_and_html(file_name_id)
        current_content_id = get_md5(self.body.encode("utf-8"))

        if content_html is None or old_content_id != current_content_id:
            content_html = md2html_by_github(self.body)
            HtmlCache.instance().set_content_id_and_html(file_name_id, current_content_id, content_html)

        return content_html

    @cached_property
    def meta(self):
        """A dict of metadata parsed as YAML from the header of the file.
        """
        meta = yaml.safe_load(self._meta)
        # YAML documents can be any type but we want a dict
        # eg. yaml.safe_load('') -> None
        #     yaml.safe_load('- 1\n- a') -> [1, 'a']
        if not meta:
            if self._meta:
                # 还原body
                self.body = "\n".join((self._meta, self.body))

            meta = {}

        if not isinstance(meta, dict):
            raise ValueError("Excpected a dict in metadata for '{0}', got {1}".
                             format(self.path, type(meta).__name__))

        # title
        if "title" not in meta:
            _title = None
            if self._meta:
                _title = self._meta.replace("#", "").strip()

            if _title is None:
                _title = os.path.basename(self.path)

            meta["title"] = _title or "日志"

        # date
        if "date" not in meta:
            meta["date"] = self._get_date_from_path(self.path) or datetime.date.today()

        return meta

    def _get_date_from_path(self, path):
        """
            文件命名: /2018/01/31/xxx.md
        :rtype: datetime.date
        """
        result = self.date_re.findall(path)
        if result:
            return datetime.datetime.strptime(result[0], "%Y/%m/%d").date()
        return None


def flat_pages_parse(self, content, path):
    """Parse a flatpage file, i.e. read and parse its meta data and body.

    :return: initialized :class:`Page` instance.
    """
    lines = iter(content.split('\n'))

    # Read lines until an empty line is encountered.
    meta = '\n'.join(takewhile(operator.methodcaller('strip'), lines))
    # The rest is the content. `lines` is an iterator so it continues
    # where `itertools.takewhile` left it.
    content = '\n'.join(lines)

    # Now we ready to get HTML renderer function
    html_renderer = self.config('html_renderer')

    # If function is not callable yet, import it
    if not callable(html_renderer):
        html_renderer = import_string(html_renderer)

    # Make able to pass custom arguments to renderer function
    html_renderer = self._smart_html_renderer(html_renderer)

    # Initialize and return Page instance
    return Page(path, meta, content, html_renderer)


__all__ = ("md2html_by_github", "flat_pages_parse", "Page", "HtmlCache")
