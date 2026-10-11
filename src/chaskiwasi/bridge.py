# src/chaskiwasi/bridge.py
import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from chaskitambo import ChaskiDocument
from chaskiwasi.factory import ConfigurationFactory
from chaskiwasi.main import ExtractorDocumentalUniversal


class ChaskitamboChaskiwasiBridge:
    """
    Adaptador universal y agnóstico que conecta los flujos en streaming de Chaskitambo
    con el motor de análisis de Chaskiwasi, delegando las reglas de negocio a cada plugin.
    """
    def __init__(self, output_dir: str = "./salida_unificada"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.factory = ConfigurationFactory()
        if not self.factory.claves_disponibles:
            raise RuntimeError("No se detectaron plugins de configuración en 'chaskiwasi.configs'.")
            
        self.extractor_universal = ExtractorDocumentalUniversal(
            config=None,
            carpeta_base=str(self.output_dir),
            factory=self.factory
        )

    async def handle_pipeline_maestro(self, paquete_maestro: Dict[str, Any]) -> None:
        """
        Procesa y consolida un paquete completo de pipeline multi-fuente:
        documento principal (ej. Remaju) + enriquecimientos (ej. Sunarp, CEJ).
        Genera el JSON Maestro unificado definitivo en la carpeta de salida.
        """
        doc_prin: ChaskiDocument = paquete_maestro.get("documento_principal")
        enriquecimientos = paquete_maestro.get("enriquecimientos", {})
        
        if not doc_prin:
            logger.warning("[-] Paquete maestro recibido sin documento principal. Omitiendo...")
            return

        id_ext = doc_prin.id_externo
        fuente_prin = doc_prin.fuente
        logger.info(f" -> [BRIDGE-MAESTRO] Consolidando pipeline integral para ID principal: {id_ext}")

        # 1. Procesar el documento principal usando la lógica existente
        # (Esto procesa su PDF, ejecuta Gemini y fusiona con el esquema del plugin principal)
        config_plugin_prin = self.factory.obtener_por_clave(fuente_prin)
        resultado_principal_fusionado = {}

        if doc_prin.pdf_bytes and config_plugin_prin:
            self.extractor_universal.config = config_plugin_prin
            self.extractor_universal.json_schema = config_plugin_prin.json_schema
            self.extractor_universal.palabras_clave = list(config_plugin_prin.palabras_clave)

            resultado_lectura = self.extractor_universal.procesar_pdf_desde_bytes(
                doc_prin.pdf_bytes, doc_prin.nombre_archivo_sugerido
            )
            tipo_capa = resultado_lectura.get("tipo_proceso", "Capa Desconocida")
            
            logger.info(f" -> [4-CAPAS RESOLUCIÓN] El documento fue resuelto por: {tipo_capa}")
            
            scraper_metadata_prin = doc_prin.metadatos.get("detalle", doc_prin.metadatos)

            if not resultado_lectura.get("requiere_revision_manual"):
                if resultado_lectura.get("modo_vision_multimodal"):
                    resultado_ia = self.extractor_universal.ejecutar_extraccion_gemini(
                        resultado_lectura["contenido_payload"], es_archivo_completo=True, nombre_archivo=doc_prin.nombre_archivo_sugerido
                    )
                else:
                    resultado_ia = self.extractor_universal.ejecutar_extraccion_gemini(
                        resultado_lectura["contenido_payload"], es_archivo_completo=False
                    )
                resultado_principal_fusionado = config_plugin_prin.fusionar_datos(scraper_metadata_prin, resultado_ia)
            else:
                resultado_principal_fusionado = {"metadatos_scraper": scraper_metadata_prin, "requiere_revision_manual": True}
        else:
            resultado_principal_fusionado = doc_prin.metadatos

        # 2. Estructurar el JSON Maestro base
        json_maestro = {
            "id_externo_principal": id_ext,
            "fuente_principal": fuente_prin,
            "documento_principal": resultado_principal_fusionado,
            "enriquecimientos_consolidados": {}
        }

        # 3. Procesar y adjuntar los enriquecimientos secundarios (Sunarp, CEJ, etc.)
        for plugin_name, datos_enriquecimiento in enriquecimientos.items():
            llave_usada = datos_enriquecimiento.get("llave_usada")
            cardinality = datos_enriquecimiento.get("cardinality")
            items_por_valor = datos_enriquecimiento.get("items_por_valor", {})

            # Estructura contenedor para este plugin secundario
            enriquecimiento_procesado = {
                "llave_usada": llave_usada,
                "cardinality": cardinality,
                "registros": {}
            }

            config_plugin_sec = self.factory.obtener_por_clave(plugin_name)

            for val_llave, lista_docs_secundarios in items_por_valor.items():
                items_analizados_para_esta_llave = []

                for doc_sec in lista_docs_secundarios:
                    # Si el documento secundario contiene un PDF adjunto, lo pasamos por IA/Extractor universal
                    if isinstance(doc_sec, ChaskiDocument) and doc_sec.pdf_bytes and config_plugin_sec:
                        self.extractor_universal.config = config_plugin_sec
                        self.extractor_universal.json_schema = config_plugin_sec.json_schema
                        self.extractor_universal.palabras_clave = list(config_plugin_sec.palabras_clave)

                        res_lec_sec = self.extractor_universal.procesar_pdf_desde_bytes(
                            doc_sec.pdf_bytes, doc_sec.nombre_archivo_sugerido
                        )
                        meta_sec = doc_sec.metadatos.get("detalle", doc_sec.metadatos)

                        if not res_lec_sec.get("requiere_revision_manual"):
                            res_ia_sec = self.extractor_universal.ejecutar_extraccion_gemini(
                                res_lec_sec["contenido_payload"], es_archivo_completo=True
                            )
                            fusion_sec = config_plugin_sec.fusionar_datos(meta_sec, res_ia_sec)
                            items_analizados_para_esta_llave.append(fusion_sec)
                        else:
                            items_analizados_para_esta_llave.append({"metadatos": meta_sec, "requiere_revision_manual": True})
                    else:
                        # Si es un diccionario plano o metadatos puros sin PDF propio que analizar
                        items_analizados_para_esta_llave.append(doc_sec)

                enriquecimiento_procesado["registros"][val_llave] = items_analizados_para_esta_llave

            json_maestro["enriquecimientos_consolidados"][plugin_name] = enriquecimiento_procesado

        # 4. Persistencia del JSON Maestro Definitivo
        ruta_destino = self.output_dir / f"{id_ext}_maestro_unificado.json"
        with open(ruta_destino, "w", encoding="utf-8") as f:
            json.dump(json_maestro, f, indent=2, ensure_ascii=False)

        logger.success(f"[★★★ JSON MAESTRO GENERADO ★★★] Expediente {id_ext} unificado con éxito en: {ruta_destino.name}")

    async def handle_document(self, document: ChaskiDocument) -> None:
        """
        Método adaptador universal que procesa cualquier ChaskiDocument independiente de su fuente.
        """
        id_ext = document.id_externo
        fuente = document.fuente
        pdf_bytes = document.pdf_bytes
        nombre_sugerido = document.nombre_archivo_sugerido
        scraper_metadata = document.metadatos.get("detalle", document.metadatos)

        logger.info(f" -> [BRIDGE] Procesando documento ID: {id_ext} | Fuente: {fuente}")

        if not pdf_bytes:
            logger.warning(f"[-] El documento {id_ext} no contiene bytes válidos. Omitiendo...")
            return

        # 1. Seleccionar la configuración específica basada en la fuente del documento (ej. 'remaju', 'sunarp')
        config_plugin = self.factory.obtener_por_clave(fuente)
        if not config_plugin:
            logger.error(f"[-] No se encontró una configuración de Chaskiwasi para la fuente '{fuente}'.")
            return

        # Asignar la configuración activa al procesador universal
        self.extractor_universal.config = config_plugin
        self.extractor_universal.json_schema = config_plugin.json_schema
        self.extractor_universal.palabras_clave = list(config_plugin.palabras_clave)

        # 2. Procesar el PDF mediante el motor de 4 capas
        resultado_lectura = self.extractor_universal.procesar_pdf_desde_bytes(pdf_bytes, nombre_sugerido)
        
        if resultado_lectura.get("requiere_revision_manual"):
            logger.warning(f"[-] Documento {id_ext} derivado a revisión manual. Motivo: {resultado_lectura.get('motivo')}")
            self._guardar_json_salida(id_ext, {
                "id_externo": id_ext,
                "fuente": fuente,
                "metadatos_scraper": scraper_metadata,
                "requiere_revision_manual": True,
                "motivo": resultado_lectura.get("motivo")
            })
            return

        # 3. Extracción profunda asistida por IA (Gemini) usando el esquema del plugin
        if resultado_lectura.get("modo_vision_multimodal"):
            resultado_ia = self.extractor_universal.ejecutar_extraccion_gemini(
                resultado_lectura["contenido_payload"],
                es_archivo_completo=True,
                nombre_archivo=nombre_sugerido
            )
        else:
            resultado_ia = self.extractor_universal.ejecutar_extraccion_gemini(
                resultado_lectura["contenido_payload"],
                es_archivo_completo=False
            )

        # 4. POLIMORFISMO: Delegar la fusión de datos exclusivamente al plugin activo
        registro_fusionado = config_plugin.fusionar_datos(scraper_metadata, resultado_ia)
        
        # Inyectar metadatos estándar de trazabilidad
        registro_fusionado["id_externo"] = id_ext
        registro_fusionado["fuente"] = fuente

        # 5. Persistencia del resultado unificado
        self._guardar_json_salida(id_ext, registro_fusionado)
        logger.success(f"[✓] Registro unificado generado y almacenado con éxito para ID: {id_ext}")

    def _guardar_json_salida(self, id_ext: str, data: Dict[str, Any]):
        ruta_destino = self.output_dir / f"{id_ext}_unificado.json"
        with open(ruta_destino, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)