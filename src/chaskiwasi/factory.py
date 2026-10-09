# factory.py
import importlib.metadata
import sys
from typing import Dict, Type, Optional
from .contract import BaseExtractionConfig


class ConfigurationFactory:
    def __init__(self):
        self._configs: Dict[str, Type[BaseExtractionConfig]] = {}
        self._cargar_plugins()

    def _cargar_plugins(self):
        """Descubre automáticamente todos los plugins instalados vía pip 
        que pertenezcan al grupo 'chaskiwasi.configs'.
        """
        grupo_plugin = "chaskiwasi.configs"
        
        # Compatibilidad con distintas versiones de Python
        if sys.version_info >= (3, 10):
            entry_points = importlib.metadata.entry_points(group=grupo_plugin)
        else:
            entry_points = importlib.metadata.entry_points().get(grupo_plugin, [])

        for ep in entry_points:
            try:
                # Carga la clase de configuración expuesta por el paquete externo
                config_cls = ep.load()
                self._configs[ep.name] = config_cls
                print(f"[Plugin Cargado] -> '{ep.name}' desde el paquete '{ep.dist.name}'")
            except Exception as e:
                print(f"[!] Error cargando el plugin {ep.name}: {str(e)}")

    def registrar_configuracion(self, clave: str, config_cls: Type[BaseExtractionConfig]):
        """Permite registro manual si se requiere en tiempo de ejecución."""
        self._configs[clave] = config_cls

    def obtener_por_clave(self, clave: str) -> BaseExtractionConfig:
        if clave not in self._configs:
            raise ValueError(f"Configuración '{clave}' no encontrada. Disponibles: {list(self._configs.keys())}")
        return self._configs[clave]()

    def autodetectar_configuracion(self, texto_muestra: str) -> BaseExtractionConfig:
        """Analiza el texto introductorio del PDF y selecciona automáticamente
        la configuración correcta evaluando las palabras clave de todos los plugins cargados.
        """
        mejor_coincidencia: Optional[BaseExtractionConfig] = None
        max_coincidencias = 0

        for config_cls in self._configs.values():
            instancia = config_cls()
            coincidencias = sum(1 for kw in instancia.palabras_clave if kw.lower() in texto_muestra.lower())
            if coincidencias > max_coincidencias:
                max_coincidencias = coincidencias
                mejor_coincidencia = instancia

        if mejor_coincidencia and max_coincidencias >= 2:
            return mejor_coincidencia

        # Fallback si no encuentra coincidencias claras (toma la primera disponible)
        if self._configs:
            primera_clave = list(self._configs.keys())[0]
            return self._configs[primera_clave]()
            
        raise ValueError("No hay configuraciones ni plugins de extracción disponibles.")