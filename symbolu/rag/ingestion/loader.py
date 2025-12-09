"""
Symbol-U RAG v3.0 - Document Loader
===================================
Loads documents from files or directories.
Supports .txt and .md files. Pure Python, no dependencies.
"""

import os
from pathlib import Path
from typing import List

from ..utils.types import Document


def load_documents(path: str) -> List[Document]:
    """
    Load documents from a file or directory.
    
    Args:
        path: Path to a single file (.txt, .md) or a directory
              containing .txt/.md files
    
    Returns:
        List of Document objects with text and metadata
    
    Raises:
        FileNotFoundError: If path doesn't exist
        ValueError: If no supported files found
    
    Examples:
        >>> docs = load_documents("data/corpus.txt")
        >>> docs = load_documents("data/documents/")
    """
    path_obj = Path(path)
    
    if not path_obj.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    
    documents: List[Document] = []
    
    if path_obj.is_file():
        # Single file
        doc = _load_single_file(path_obj)
        if doc:
            documents.append(doc)
    elif path_obj.is_dir():
        # Directory - load all supported files
        for file_path in sorted(path_obj.iterdir()):
            if file_path.is_file():
                doc = _load_single_file(file_path)
                if doc:
                    documents.append(doc)
    
    if not documents:
        raise ValueError(f"No supported files (.txt, .md) found at: {path}")
    
    return documents


def _load_single_file(file_path: Path) -> Document | None:
    """
    Load a single file if it's a supported format.
    
    Args:
        file_path: Path object to the file
    
    Returns:
        Document object or None if unsupported format
    """
    supported_extensions = {".txt", ".md", ".markdown"}
    
    if file_path.suffix.lower() not in supported_extensions:
        return None
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        
        # Skip empty files
        if not text.strip():
            return None
        
        metadata = {
            "source": str(file_path.absolute()),
            "filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "size_bytes": len(text.encode("utf-8"))
        }
        
        return Document(text=text, metadata=metadata)
    
    except (IOError, UnicodeDecodeError) as e:
        # Skip files that can't be read
        return None


def load_text(text: str, source: str = "inline") -> Document:
    """
    Create a Document from raw text string.
    
    Args:
        text: Raw text content
        source: Optional source identifier
    
    Returns:
        Document object
    
    Examples:
        >>> doc = load_text("Hello world", source="user_input")
    """
    return Document(
        text=text,
        metadata={
            "source": source,
            "filename": None,
            "extension": None,
            "size_bytes": len(text.encode("utf-8"))
        }
    )
