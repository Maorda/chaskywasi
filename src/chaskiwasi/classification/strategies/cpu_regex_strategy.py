"""Clasificación determinista mediante expresiones regulares."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Pattern

from chaskiwasi.classification.strategies.base_strategy import (
    BaseStrategy,
    ClassificationContext,
    ClassificationResult,
)


@dataclass
class RegexRule:
    source: Any
    section: Any
    patterns: List[str]
    flags: int = re.IGNORECASE | re.DOTALL
    compiled_patterns: List[Pattern[str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.compiled_patterns = []
        for pattern in self.patterns:
            try:
                self.compiled_patterns.append(re.compile(pattern, self.flags))
            except re.error as err:
                raise ValueError(
                    f"Patrón Regex inválido '{pattern}' para ({self.source}, {self.section}): {err}"
                ) from err


class CPURegexStrategy(BaseStrategy):
    """Ejecuta reglas provistas por el plugin activo, sin conocer su dominio."""

    def __init__(self, rules: Optional[List[RegexRule]] = None) -> None:
        self.rules = list(rules or [])

    def add_rule(self, rule: RegexRule) -> None:
        self.rules.append(rule)

    def classify(self, chunk: str, context: ClassificationContext) -> ClassificationResult:
        if not isinstance(chunk, str) or not chunk.strip():
            return ClassificationResult.no_match("chunk vacío")

        for rule in self.rules:
            if context.current_source is not None and rule.source != context.current_source:
                continue
            if any(pattern.search(chunk) for pattern in rule.compiled_patterns):
                return ClassificationResult(
                    source=rule.source,
                    section=rule.section,
                    matched=True,
                    reason="regex_contextual",
                )

        for rule in self.rules:
            if context.current_source is not None and rule.source == context.current_source:
                continue
            if any(pattern.search(chunk) for pattern in rule.compiled_patterns):
                return ClassificationResult(
                    source=rule.source,
                    section=rule.section,
                    matched=True,
                    reason="regex_global",
                )

        return ClassificationResult.no_match("sin coincidencia regex")
