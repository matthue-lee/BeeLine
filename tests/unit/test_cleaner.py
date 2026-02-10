import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.ingestion.cleaner import ContentCleaner


def test_cleaner_removes_share_and_footer():
    cleaner = ContentCleaner()
    html = """
    <article>
        <div class="share">Share this</div>
        <p>Prime Minister announced funding.</p>
        <p>Media Contact: Example</p>
    </article>
    """

    result = cleaner.clean(html)

    assert "Share this" not in (result.text or "")
    assert "Media Contact" not in (result.text or "")
    assert result.word_count >= 4
    assert "div.share" in result.removed_sections
    assert result.excerpt.startswith("Prime Minister")


def test_cleaner_handles_empty_html():
    cleaner = ContentCleaner()

    result = cleaner.clean(None)

    assert result.text is None
    assert result.word_count == 0
