import os
from pathlib import Path
from typing import List, Dict, Any
import datetime

from jinja2 import Template
from bs4 import BeautifulSoup
from mutagen.mp3 import MP3

from papercast.production import Production
from papercast.base import BasePublisher

PODCAST_TEMPLATE = """
<rss xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:googleplay="http://www.google.com/schemas/play-podcasts/1.0" xmlns:media="http://www.rssboard.org/media-rss" version="2.0">
    <channel>
        <title>{{title}}</title>
        <link>{{base_url}}</link>
        <language>{{language}}</language>
        <atom:link href="{{xml_link}}" rel="self" type="application/rss+xml"/>
        <copyright>{{copyright}}</copyright>
        <itunes:subtitle>{{subtitle}}</itunes:subtitle>
        <itunes:author>{{author}}</itunes:author>
        <itunes:summary>{{description}}</itunes:summary>
        <itunes:keywords>{{keywords}}</itunes:keywords>
        <description>{{description}}</description>
        <itunes:owner><itunes:name>{{author}}</itunes:name><itunes:email>{{email}}</itunes:email></itunes:owner>
        <itunes:image href="{{cover_path}}"/>
        {% for category in categories %}
        <itunes:category text="{{category}}"></itunes:category>
        {% endfor %}
    </channel>
</rss>
"""

EPISODE_TEMPLATE = """
        <item>
        <title>{{title}}</title>
        <itunes:title>{{title}}</itunes:title>
        <itunes:author>{{author}}</itunes:author>
        <itunes:subtitle>{{subtitle}}</itunes:subtitle>
        <itunes:summary><![CDATA[{{description}}]]></itunes:summary>
        <description><![CDATA[{{description}}]]></description>
        <enclosure url="{{mp3path}}" length="{{duration}}" type="audio/mpeg"/>
        <itunes:duration>{{duration}}</itunes:duration>
        <itunes:season>{{season}}</itunes:season>
        <itunes:episode>{{episode}}</itunes:episode>
        <itunes:episodeType>full</itunes:episodeType>
        <guid isPermaLink="false">{{mp3path}}</guid>
        <pubDate>{{publish_date}}</pubDate>
        <itunes:explicit>NO</itunes:explicit>
        </item>
"""


class GithubPagesPodcastPublisher(BasePublisher):
    def __init__(
        self,
        xml_path: str,
        title: str,
        base_url: str,
        language: str,
        copyright: str,
        subtitle: str,
        author: str,
        description: str,
        email: str,
        cover_path: str,
        categories: List[str],
        keywords: List[str],
        template: str = PODCAST_TEMPLATE,
        episode_template: str = EPISODE_TEMPLATE,
    ) -> None:
        super().__init__()
        self.xml_path = Path(xml_path)
        self.podcast_template = Template(template)
        self.episode_template = Template(episode_template)
        self.podcast_template.render(
            title=title,
            base_url=base_url,
            language=language,
            copyright=copyright,
            subtitle=subtitle,
            author=author,
            description=description,
            email=email,
            cover_path=cover_path,
            categories=categories,
            keywords=", ".join(keywords),
        )

        if not self.xml_path.exists():
            self.xml_path.parent.mkdir(parents=True, exist_ok=True)
            xml_content = self.podcast_template.render(
                epsode_meta=[],
            )
            self.xml_path.write_text(xml_content)

    def input_types(self) -> Dict[str, Any]:
        return {
            "mp3_path": str,
            "title": str,
            "description": str,
        }

    def _get_mp3_size_length(self, mp3_path: str):
        statinfo = os.stat(mp3_path)
        size = str(statinfo.st_size)

        audio = MP3(mp3_path)
        length = str(audio.info.length)

        return size, length

    def process(self, production: Production, **kwargs):
        size, length = self._get_mp3_size_length(production.mp3_path)

        old_xml = self.xml_path.read_text()
        soup = BeautifulSoup(old_xml, "xml")

        episodes = list(soup.find_all("item"))

        if len(episodes) > 0:
            episode_nums = [int(e.find("itunes:episode").string) for e in episodes]
            episode_num = max(episode_nums) + 1
        else:
            episode_num = 1

        episode_meta = {
            "title": production.title,
            "subtitle": "",
            "description": production.description,
            "mp3path": self.base_url + production.mp3_path,
            "duration": str(length),
            "season": 1,  # TODO
            "episode": episode_num,
            # "publish_date": datetime.datetime.now().strftime(
            #     "%a, %d %b %Y %H:%M:%S %z"
            # ), # TODO
        }

        episode_xml = self.episode_template.render(episode_meta)
        # print(episode_xml)
        # print(type(episode_xml))
        # quit()

        channel = soup.find("channel")

        if channel is None:
            raise ValueError("No channel found in podcast xml")

        channel.insert(-1, BeautifulSoup(episode_xml).find("item"))

        self.xml_path.write_text(str(soup))
