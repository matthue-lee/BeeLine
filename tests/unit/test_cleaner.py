import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.ingestion.cleaner import ContentCleaner


def test_cleaner_extracts_ministers_tags_and_published_date():
    cleaner = ContentCleaner()
    html = """
    <html>
      <head>
        <title>Sample Release</title>
      </head>
      <body>
        <article>
          <h1 class="article__title">Ngāti Whātua Ōrākei led charter school gives students more options</h1>
          <time class="meta meta__date" datetime="">
            <time datetime="2026-02-22T22:56:49Z">23 February 2026</time>
          </time>
          <div class="field--name-field-minister">
            <div class="field__item"><a>Hon Example Minister</a></div>
          </div>
          <div class="field minister__title">
            <div class="field__item">Hon David Seymour</div>
          </div>
          <div class="field--name-field-tags">
            <div class="field__item"><a>Economy</a></div>
            <div class="field__item"><a>Budget 2025</a></div>
          </div>
          <em class="tag tag--portfolio">
            <div class="tag taxonomy-term taxonomy-term--type-portfolios taxonomy-term--view-mode-teaser-small ds-1col clearfix">
              <a href="/portfolio/.../education" hreflang="en">Education</a>
            </div>
          </em>
          <p>Some important policy announcement content.</p>
        </article>
      </body>
    </html>
    """

    result = cleaner.clean(html)

    assert result.metadata["ministers"] == ["Hon Example Minister", "Hon David Seymour"]
    assert result.metadata["tags"] == ["Economy", "Budget 2025", "Education"]
    assert result.metadata["published_at"] == ["2026-02-22T22:56:49+00:00"]
