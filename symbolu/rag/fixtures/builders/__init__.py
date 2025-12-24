"""
RAG Mockup Corpus Builders
==========================

Builders for generating realistic mockup corpora for RAG testing.

Available Corpora:
- history: American History (Colonial era to modern)
- news: Current Events / News (politics, tech, climate)
- science: Science & Physics (physics, chemistry, astronomy)
- biology: Biology & Medicine (body, genetics, diseases)
- finance: Finance & Economics (markets, personal finance)
- literature: English Literature (Shakespeare to modern)
"""

from .base import CorpusBuilder, DocumentSpec
from .history_builder import HistoryCorpusBuilder
from .news_builder import NewsCorpusBuilder
from .science_builder import ScienceCorpusBuilder
from .biology_builder import BiologyCorpusBuilder
from .finance_builder import FinanceCorpusBuilder
from .literature_builder import LiteratureCorpusBuilder

__all__ = [
    "CorpusBuilder",
    "DocumentSpec",
    "HistoryCorpusBuilder",
    "NewsCorpusBuilder",
    "ScienceCorpusBuilder",
    "BiologyCorpusBuilder",
    "FinanceCorpusBuilder",
    "LiteratureCorpusBuilder",
]
