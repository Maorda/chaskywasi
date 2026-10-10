# contract.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Type, Tuple
from pydantic import BaseModel, ValidationError


class BaseExtractionConfig(ABC):

    @property
    @abstractmethod
    def model_class(self) -> Type[BaseModel]:
        """Clase Pydantic que define el esquema de los datos a extraer."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Modelo de Gemini a utilizar (ej: 'gemini-2.5-flash')."""
        pass

    @property
    @abstractmethod
    def prompt_extraccion(self) -> str:
        """Prompt especializado para el tipo de documento."""
        pass

    @property
    @abstractmethod
    def palabras_clave(self) -> List[str]:
        """Lista de palabras clave para validar suficiencia del texto extraído."""
        pass

    @property
    def json_schema(self) -> Dict[str, Any]:
        """Genera dinámicamente el JSON Schema desde la clase Pydantic."""
        schema = self.model_class.model_json_schema()
        # Limpieza opcional de metadatos de Pydantic v2 no requeridos por Gemini API
        schema.pop("title", None)
        return schema

    @property
    def campos_requeridos(self) -> List[str]:
        """Obtiene dinámicamente los campos definidos en la estructura Pydantic."""
        return list(self.model_class.model_fields.keys())

    def validar_y_estructurar(self, data_json: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """Valida la respuesta devuelta por el LLM contra el modelo Pydantic.
        Devuelve una tupla (datos_validados_dict, lista_campos_faltantes).
        """
        campos_faltantes = []
        datos_procesados = {}

        try:
            # Intenta instanciar y validar con Pydantic
            instancia_validada = self.model_class.model_validate(data_json)
            datos_procesados = instancia_validada.model_dump()
        except ValidationError:
            # Si falla la validación estricta, mapea campo por campo
            for campo in self.campos_requeridos:
                valor = data_json.get(campo)
                if valor in [None, "", [], {}]:
                    campos_faltantes.append(campo)
                    datos_procesados[campo] = None
                else:
                    datos_procesados[campo] = valor

        # Detección adicional de valores nulos o vacíos
        if not campos_faltantes:
            for campo, valor in datos_procesados.items():
                if valor in [None, "", [], {}]:
                    campos_faltantes.append(campo)

        return datos_procesados, campos_faltantes

    @abstractmethod
    def extraer_identificador(self, texto: str) -> str:
        """Estrategia regex para obtener el identificador primario del documento."""
        pass

    def fusionar_datos(self, scraper_metadata: Dict[str, Any], ai_extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estrategia por defecto de fusión. Cada plugin puede sobrescribir este método
        para aplicar reglas de negocio específicas sin acoplar el núcleo.
        """
        registro_unificado = dict(scraper_metadata)
        datos_ia = ai_extraction_result.get("datos_extraidos", {})
        
        # Fusión genérica estándar
        registro_unificado["datos_extraidos_ia"] = datos_ia
        registro_unificado["analisis_metadata"] = {
            "campos_faltantes_ia": ai_extraction_result.get("campos_faltantes", []),
            "completado_exitosamente": ai_extraction_result.get("completado_exitosamente", False)
        }
        return registro_unificado