import hashlib
from pathlib import Path
from urllib.parse import urlparse
import scrapy


class HtwEnSpider(scrapy.Spider):
    name = "htw_en"
    allowed_domains = ["www.htw-berlin.de"]
    start_urls = ["https://www.htw-berlin.de/en/"]

    custom_settings = {
        "FEEDS": {
            "outputs/manifest.jl": {
                "format": "jsonlines",
                "encoding": "utf8",
            }
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshot_dir = Path("snapshots_raw")
        self.snapshot_dir.mkdir(exist_ok=True)

    def is_english_page(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc == "www.htw-berlin.de" and parsed.path.startswith("/en/")

    def make_id(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    def parse(self, response):
        url = response.url

        if not self.is_english_page(url):
            return

        page_id = self.make_id(url)

        # Save raw HTML
        html_path = self.snapshot_dir / f"{page_id}.html"
        html_path.write_bytes(response.body)

        # Save metadata
        yield {
            "id": page_id,
            "url": url,
            "status": response.status,
            "content_type": response.headers.get("Content-Type", b"").decode(),
            "html_file": str(html_path),
            "title": response.css("title::text").get(),
        }

        # Follow internal English links
        for href in response.css("a::attr(href)").getall():
            next_url = response.urljoin(href)
            if self.is_english_page(next_url):
                yield scrapy.Request(next_url, callback=self.parse)
