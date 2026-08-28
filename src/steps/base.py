from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime


class BaseStep(ABC):
    def __init__(self, config: dict, work_dir: Path):
        self.config = config
        self.work_dir = work_dir

    @abstractmethod
    def run(self, **inputs) -> dict:
        """Run step, return output paths/data as dict."""
        ...

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{self.__class__.__name__}] {msg}")

    def ensure_dir(self, subdir: str) -> Path:
        """Create and return a subdirectory under work_dir."""
        path = self.work_dir / subdir
        path.mkdir(parents=True, exist_ok=True)
        return path
