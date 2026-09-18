import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Pattern, Tuple
from chaskiwasi.classification.strategies.base_strategy import BaseStrategy


@dataclass
class RegexRule:
    """Estructura de datos para definir reglas de clasificación por Regex."""
    source: Any
    section: Any
    patterns: List[str]
    flags: int = re.IGNORECASE | re.DOTALL
    compiled_patterns: List[Pattern[str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        compiled: List[Pattern[str]] = []
        for pattern in self.patterns:
            try:
                compiled.append(re.compile(pattern, self.flags))
            except re.error as err:
                raise ValueError(
                    f"Patrón Regex inválido '{pattern}' para la regla ({self.source}, {self.section}): {err}"
                ) from err
        self.compiled_patterns = compiled


class CPURegexStrategy(BaseStrategy):
    """Estrategia genérica que ejecuta reglas Regex inyectadas."""

    def __init__(self, rules: Optional[List[RegexRule]] = None) -> None:
        self.rules: List[RegexRule] = list(rules) if rules else []

    def add_rule(self, rule: RegexRule) -> None:
        """Permite registrar reglas dinámicamente."""
        self.rules.append(rule)

    def classify(
        self,
        chunk_text: str,
        current_source: Optional[Any] = None,
    ) -> Tuple[Optional[Any], Optional[Any]]:
        if not isinstance(chunk_text, str) or not chunk_text:
            return None, None

        # Evaluación con preferencia contextual por current_source si aplica
        for rule in self.rules:
            if current_source and rule.source != current_source:
                continue
                
            if any(pattern.search(chunk_text) for pattern in rule.compiled_patterns):
                return rule.source, rule.section

        # Segunda pasada para reglas generales si no coincidió en el contexto actual
        if current_source:
            for rule in self.rules:
                if rule.source == current_source:
                    continue
                if any(pattern.search(chunk_text) for pattern in rule.compiled_patterns):
                    return rule.source, rule.section

        return None, None