# factory.py
"""Descubrimiento y selección explícita de configuraciones de extracción."""

import importlib.metadata
import sys
from typing import Dict, List, Optional, Type

from .contract import BaseExtractionConfig


class ConfigurationFactory:
    """Carga plugins instalados y selecciona una configuración sin fallback silencioso."""

    GRUPO_PLUGINS = "chaskiwasi.plugins"
    MIN_COINCIDENCIAS = 2

    def __init__(self) -> None:
        self._configs: Dict[str, Type[BaseExtractionConfig]] = {}
        self._cargar_plugins()

    @property
    def claves_disponibles(self) -> tuple[str, ...]:
        """Nombres de los plugins cargados, en orden de registro."""
        return tuple(self._configs.keys())

    def _obtener_entry_points(self):
        """Obtiene entry points de forma compatible con distintas versiones de Python."""
        entry_points = importlib.metadata.entry_points()
        if hasattr(entry_points, "select"):
            return entry_points.select(group=self.GRUPO_PLUGINS)
        return entry_points.get(self.GRUPO_PLUGINS, [])

    def _cargar_plugins(self) -> None:
        for entry_point in self._obtener_entry_points():
            try:
                config_cls = entry_point.load()
                self.registrar_configuracion(entry_point.name, config_cls)
                distribucion = getattr(getattr(entry_point, "dist", None), "name", "desconocida")
                print(
                    f"[Plugin Cargado] -> '{entry_point.name}' "
                    f"desde el paquete '{distribucion}'"
                )
            except Exception as exc:
                print(f"[!] Error cargando el plugin '{entry_point.name}': {exc}")

    def registrar_configuracion(
        self,
        clave: str,
        config_cls: Type[BaseExtractionConfig],
    ) -> None:
        """Registra una clase de configuración validando su contrato."""
        if not isinstance(clave, str) or not clave.strip():
            raise ValueError("La clave del plugin debe ser una cadena no vacía.")
        if not isinstance(config_cls, type) or not issubclass(config_cls, BaseExtractionConfig):
            raise TypeError(
                f"El plugin '{clave}' debe ser una clase derivada de BaseExtractionConfig."
            )

        instancia = config_cls()
        for atributo in (
            "model_class",
            "model_name",
            "palabras_clave",
            "prompt_extraccion",
            "extraer_identificador",
            "validar_y_estructurar",
            "campos_requeridos",
            "json_schema",
        ):
            if not hasattr(instancia, atributo):
                raise TypeError(
                    f"El plugin '{clave}' no cumple el contrato: falta '{atributo}'."
                )

        palabras = instancia.palabras_clave
        if not isinstance(palabras, (list, tuple)) or not palabras:
            raise ValueError(
                f"El plugin '{clave}' debe declarar palabras_clave como lista no vacía."
            )
        self._configs[clave] = config_cls

    def obtener_por_clave(self, clave: str) -> BaseExtractionConfig:
        try:
            config_cls = self._configs[clave]
        except KeyError as exc:
            disponibles = ", ".join(self.claves_disponibles) or "(ninguno)"
            raise ValueError(
                f"Configuración '{clave}' no encontrada. Disponibles: {disponibles}"
            ) from exc
        return config_cls()

    @staticmethod
    def _normalizar(texto: str) -> str:
        return " ".join((texto or "").casefold().split())

    def autodetectar_configuracion(self, texto_muestra: str) -> BaseExtractionConfig:
        """Selecciona el plugin con mayor coincidencia; nunca escoge uno por defecto."""
        texto = self._normalizar(texto_muestra)
        if not texto:
            raise LookupError(
                "No hay texto suficiente para autodetectar el plugin. "
                "El documento requiere revisión manual o una selección explícita."
            )
        if not self._configs:
            raise LookupError("No hay configuraciones ni plugins de extracción disponibles.")

        puntuaciones: list[tuple[int, str, Type[BaseExtractionConfig]]] = []
        for clave, config_cls in self._configs.items():
            config = config_cls()
            palabras = {
                self._normalizar(palabra)
                for palabra in config.palabras_clave
                if isinstance(palabra, str) and palabra.strip()
            }
            coincidencias = sum(1 for palabra in palabras if palabra in texto)
            puntuaciones.append((coincidencias, clave, config_cls))

        puntuaciones.sort(key=lambda elemento: elemento[0], reverse=True)
        mejor_puntuacion, mejor_clave, mejor_clase = puntuaciones[0]

        if mejor_puntuacion < self.MIN_COINCIDENCIAS:
            resumen = ", ".join(
                f"{clave}={puntuacion}" for puntuacion, clave, _ in puntuaciones
            )
            raise LookupError(
                "Ningún plugin alcanzó el mínimo de coincidencias "
                f"({self.MIN_COINCIDENCIAS}). Puntuaciones: {resumen}"
            )

        empatados = [
            clave
            for puntuacion, clave, _ in puntuaciones
            if puntuacion == mejor_puntuacion
        ]
        if len(empatados) > 1:
            raise LookupError(
                "Autodetección ambigua: varios plugins obtuvieron la misma puntuación "
                f"({mejor_puntuacion}): {', '.join(empatados)}. "
                "Registra una regla de desempate o selecciona el plugin explícitamente."
            )

        print(
            f"[Plugin Detectado] -> '{mejor_clave}' "
            f"({mejor_puntuacion} coincidencias)"
        )
        return mejor_clase()
