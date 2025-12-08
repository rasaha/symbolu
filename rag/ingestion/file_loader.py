"""
File Loader
============

Loads files from various formats.
"""

from pathlib import Path
from typing import Tuple


class FileLoader:
    """Loads files from disk."""
    
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
    
    def load(self, path: str) -> Tuple[str, dict]:
        """
        Load file and return content with metadata.
        
        Returns:
            Tuple of (content, metadata)
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")
        
        content = self._load_by_extension(path, ext)
        metadata = {
            "filename": path.name,
            "extension": ext,
            "size": path.stat().st_size
        }
        
        return content, metadata
    
    def _load_by_extension(self, path: Path, ext: str) -> str:
        """Load file based on extension."""
        if ext in {".txt", ".md"}:
            return path.read_text(encoding="utf-8")
        elif ext == ".pdf":
            return self._load_pdf(path)
        elif ext == ".docx":
            return self._load_docx(path)
        return ""
    
    def _load_pdf(self, path: Path) -> str:
        """Load PDF file."""
        # Placeholder - implement PDF loading
        raise NotImplementedError("PDF loading pending.")
    
    def _load_docx(self, path: Path) -> str:
        """Load DOCX file."""
        # Placeholder - implement DOCX loading
        raise NotImplementedError("DOCX loading pending.")
