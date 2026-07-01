"""Unified experiment interface.

Every experiment subclasses :class:`Experiment` and implements the lifecycle:
``prepare() -> run() -> validate() -> summarize() -> export_report()``.
``execute()`` orchestrates them, timing the run and attaching reproducibility
metadata + the output hash automatically (no manual bookkeeping).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, is_dataclass

from . import repro
from .report import ReportBuilder


class Experiment(ABC):
    #: short title for the report header
    title: str = "Experiment"
    #: STATUS/caveat line placed at the top of every report
    caveat: str = ("STRUCTURAL / SYNTHETIC CALIBRATION ONLY — no semantics, no real data, "
                   "no A′, no B–G, no PASS/FAIL/⊥ for Symbol-U. Stage A frozen.")

    def __init__(self, config, seed: int | None = None):
        self.config = config
        self.seed = seed
        self.context: dict = {}
        self.results: dict = {}

    # ---- lifecycle (override) ----
    @abstractmethod
    def prepare(self) -> None: ...
    @abstractmethod
    def run(self) -> None: ...
    def validate(self) -> None: ...
    @abstractmethod
    def summarize(self) -> dict: ...
    @abstractmethod
    def build_report(self, rb: ReportBuilder) -> None: ...

    # ---- orchestration ----
    def execute(self, out_path) -> dict:
        with repro.timed() as t:
            self.prepare()
            self.run()
            self.validate()
            summary = self.summarize()
        cfg = asdict(self.config) if is_dataclass(self.config) else dict(self.config or {})
        rb = ReportBuilder(self.title, self.caveat)
        self.build_report(rb)
        # write once to hash, then rewrite with the repro block appended
        body = rb.build()
        meta = repro.collect_metadata(config=cfg, seed=self.seed,
                                      runtime_s=t["runtime_s"],
                                      outputs={"report_body": repro.sha256_text(body)})
        rb.repro_block(meta).footer()
        md = rb.write(out_path)
        return {"summary": summary, "metadata": meta,
                "report_path": str(out_path), "report_sha256": repro.sha256_text(md)}
