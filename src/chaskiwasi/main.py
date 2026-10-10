try:
    from chaskiwasi.factory import ConfigurationFactory
except ImportError:
    from .factory import ConfigurationFactory
import os
import json
import time
import re
import shutil
from io import BytesIO
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
import pymupdf as fitz
import numpy as np
import cv2
import pytesseract
from deskew import determine_skew
#fromconfigs import JSON_SCHEMA_EXTRACCION, PALABRAS_CLAVE_LEGALES, PATRON_EXPEDIENTE_ESTANDAR, PATRON_EXPEDIENTE_SECUNDARIO
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# 1. Definición de TESSDATA_PREFIX para los modelos de idioma
os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"
# 2. Agregar Tesseract al PATH en tiempo de ejecución para que el motor de Docling detecte tesseract.exe
os.environ["PATH"] += os.pathsep + r"C:\Program Files\Tesseract-OCR"
try:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.document import DocumentStream
    DOCLING_DISPONIBLE = True
except ImportError:
    DOCLING_DISPONIBLE = False
try:
    # Importar el mismo contrato que heredan los plugins instalados.
    from chaskiwasi.contract import BaseExtractionConfig
except ImportError:
    from .contract import BaseExtractionConfig
load_dotenv()
class ExtractorDocumentalUniversal:
    def __init__(
        self,
        config: Optional[BaseExtractionConfig] = None,
        carpeta_base: str = "./mis_pdfs",
        factory: ConfigurationFactory = None,
    ):
        self.factory = factory
        self.config = config
        self.client = genai.Client()
        self.carpeta_base = os.path.abspath(carpeta_base)
        self.carpeta_revision = os.path.join(self.carpeta_base, "revision_manual")
        os.makedirs(self.carpeta_base, exist_ok=True)
        os.makedirs(self.carpeta_revision, exist_ok=True)
        if DOCLING_DISPONIBLE:
            print("[+] Capa 2 Configurada: Motor Docling con Tesseract OCR local.")
            # Configurar opciones del pipeline de Docling
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True
            pipeline_options.ocr_options = TesseractOcrOptions(lang=["spa"])
            # Instanciar el convertidor asignando el pipeline a archivos PDF
            self.docling_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        else:
            print("[!] Advertencia: Docling no está instalado. El flujo saltará de Capa 1 a Capa 3.")
            self.docling_converter = None
        self.reporte_final = {
            "fecha_ejecucion": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_processed": 0,
            "exitosos_completos": 0,
            "con_campos_faltantes": 0,
            "enviados_a_revision_manual": 0,
            "detalles_lote": []
        }
        # La configuración puede seleccionarse por documento.
        self.json_schema = self.config.json_schema if self.config else None
        self.palabras_clave = self.config.palabras_clave if self.config else []
    def _seleccionar_configuracion_documento(self, ruta_pdf: str) -> None:
        """Selecciona una configuración para cada PDF usando texto de varias páginas."""
        if self.factory is None:
            if self.config is None:
                raise RuntimeError(
                    "No hay configuración ni ConfigurationFactory disponibles."
                )
            self.json_schema = self.config.json_schema
            self.palabras_clave = self.config.palabras_clave
            return
        with fitz.open(ruta_pdf) as documento:
            paginas_muestra = min(len(documento), 4)
            texto_muestra = "\n".join(
                documento[indice].get_text() or ""
                for indice in range(paginas_muestra)
            ).strip()

            # Los PDF escaneados no tienen texto nativo. Se usa OCR local de
            # la primera página para no bloquear el pipeline de cuatro capas.
            if not texto_muestra and len(documento):
                texto_muestra = self.ejecutar_pipeline_capa3(documento, [0]).strip()
        selector = getattr(self.factory, "autodetectar_configuracion", None)
        if not callable(selector):
            raise TypeError(
                "ConfigurationFactory debe implementar autodetectar_configuracion(texto)."
            )
        configuracion = selector(texto_muestra)
        if configuracion is None:
            raise LookupError(
                "ConfigurationFactory no encontró una configuración compatible con el PDF."
            )
        atributos_requeridos = (
            "json_schema",
            "palabras_clave",
            "extraer_identificador",
            "model_name",
            "prompt_extraccion",
            "validar_y_estructurar",
            "campos_requeridos",
        )
        faltantes = [
            nombre for nombre in atributos_requeridos
            if not hasattr(configuracion, nombre)
        ]
        if faltantes:
            raise TypeError(
                "El plugin seleccionado no cumple BaseExtractionConfig; "
                f"faltan atributos: {', '.join(faltantes)}."
            )
        self.config = configuracion
        self.json_schema = self.config.json_schema
        self.palabras_clave = list(self.config.palabras_clave)
        print(
            "    [Plugin] Configuración seleccionada: "
            f"{type(self.config).__name__}"
        )
    def _mover_pdf_a_revision(self, ruta_pdf: str, nombre_archivo: str) -> str:
        """Mueve el PDF a revisión manual sin sobrescribir archivos existentes."""
        destino = os.path.join(self.carpeta_revision, nombre_archivo)
        if os.path.exists(destino):
            base, extension = os.path.splitext(nombre_archivo)
            contador = 1
            while True:
                candidato = os.path.join(
                    self.carpeta_revision,
                    f"{base}_{contador}{extension}",
                )
                if not os.path.exists(candidato):
                    destino = candidato
                    break
                contador += 1
        shutil.move(ruta_pdf, destino)
        return destino
    def buscar_numero_expediente(self, texto: str) -> str:
        return self.config.extraer_identificador(texto)
    def procesar_con_docling(self, pdf_bytes: bytes, nombre_archivo: str) -> str:
        if not self.docling_converter:
            return ""
        try:
            pdf_stream = BytesIO(pdf_bytes)
            source = DocumentStream(name=nombre_archivo, stream=pdf_stream)
            result = self.docling_converter.convert(source)
            return result.document.export_to_markdown()
        except Exception as e:
            print(f"    [!] Error en ejecución interna de Docling: {str(e)}")
            return ""
    def corregir_inclinacion_y_ocr(self, matrix_cv: np.ndarray) -> str:
        try:
            grayscale = cv2.cvtColor(matrix_cv, cv2.COLOR_BGR2GRAY)
            angle = determine_skew(grayscale)
            if angle and abs(angle) < 45:
                (h, w) = matrix_cv.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                grayscale = cv2.warpAffine(grayscale, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            # Umbralizado Otsu para preservar mejor la estructura del texto frente a adaptiveThreshold
            _, processed_img = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return pytesseract.image_to_string(processed_img, lang='spa', config=r'--oem 3 --psm 6')
        except Exception as e:
            print(f"    [!] Error en OCR local: {str(e)}")
            return ""
    def obtener_indices_criticos(self, total_paginas: int) -> List[int]:
        if total_paginas <= 0:
            return []
        if total_paginas <= 4:
            return list(range(total_paginas))
        return [0, 1, total_paginas - 2, total_paginas - 1]
    def ejecutar_pipeline_capa3(self, doc_fitz: fitz.Document, indices_objetivo: List[int]) -> str:
        texto_consolidado = ""
        zoom = 300 / 72
        matriz_zoom = fitz.Matrix(zoom, zoom)
        for idx in indices_objetivo:
            pagina = doc_fitz[idx]
            pixmap = pagina.get_pixmap(matrix=matriz_zoom)
            img_data = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape((pixmap.h, pixmap.w, pixmap.n))
            if pixmap.n == 4:
                img_cv = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
            elif pixmap.n == 3:
                img_cv = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
            else:
                img_cv = cv2.cvtColor(img_data, cv2.COLOR_GRAY2BGR)
            texto_consolidado += self.corregir_inclinacion_y_ocr(img_cv) + "\n"
        return texto_consolidado.strip()
    def verificar_y_filtrar_pdf(self, ruta_pdf: str) -> Dict[str, Any]:
        doc_fitz = None
        try:
            with open(ruta_pdf, "rb") as f:
                pdf_bytes = f.read()
            doc_fitz = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_paginas = len(doc_fitz)
            nombre_corto = os.path.basename(ruta_pdf)
            if total_paginas == 0:
                doc_fitz.close()
                return {"requiere_revision_manual": True, "motivo": "El archivo PDF no contiene páginas."}
            if total_paginas > 50:
                doc_fitz.close()
                return {
                    "requiere_revision_manual": True,
                    "motivo": f"El archivo tiene {total_paginas} páginas (Excede el tope de 50 hojas)."
                }
            texto_primera_pagina = doc_fitz[0].get_text() or ""
            expediente = self.buscar_numero_expediente(texto_primera_pagina)
            indices_objetivo = self.obtener_indices_criticos(total_paginas)
            # Capa 1: Texto nativo PyMuPDF
            texto_completo = ""
            for idx in indices_objetivo:
                texto_completo += (doc_fitz[idx].get_text() or "") + "\n"
            if len(texto_completo.strip()) > 150 and any(p in texto_completo.lower() for p in self.palabras_clave):
                if expediente == "No detectado":
                    expediente = self.buscar_numero_expediente(texto_completo[:2000])
                doc_fitz.close()
                return {
                    "modo_vision_multimodal": False,
                    "contenido_payload": texto_completo.strip(),
                    "numero_expediente": expediente,
                    "tipo_proceso": "Capa 1 (PyMuPDF Nativo)",
                    "requiere_revision_manual": False
                }
            # Capa 2: Docling local
            print("    [!] Capa 1 insuficiente. Activando Capa 2 (Docling local)...")
            if DOCLING_DISPONIBLE:
                writer_c2 = fitz.open()
                for idx in indices_objetivo:
                    writer_c2.insert_pdf(doc_fitz, from_page=idx, to_page=idx)
                bytes_recortados_c2 = writer_c2.write()
                writer_c2.close()
                texto_completo = self.procesar_con_docling(bytes_recortados_c2, nombre_corto)
                if len(texto_completo.strip()) > 150 and any(p in texto_completo.lower() for p in self.palabras_clave):
                    expediente = self.buscar_numero_expediente(texto_completo[:2000])
                    doc_fitz.close()
                    return {
                        "modo_vision_multimodal": False,
                        "contenido_payload": texto_completo.strip(),
                        "numero_expediente": expediente,
                        "tipo_proceso": "Capa 2 (Docling Local)",
                        "requiere_revision_manual": False
                    }
            # Capa 3: OCR Tesseract local
            print("    [!] Capa 2 insuficiente o ausente. Activando Capa 3 (OCR Local Tesseract)...")
            texto_completo = self.ejecutar_pipeline_capa3(doc_fitz, indices_objetivo)
            if len(texto_completo.strip()) > 150 and any(p in texto_completo.lower() for p in self.palabras_clave):
                expediente = self.buscar_numero_expediente(texto_completo[:2000])
                doc_fitz.close()
                return {
                    "modo_vision_multimodal": False,
                    "contenido_payload": texto_completo.strip(),
                    "numero_expediente": expediente,
                    "tipo_proceso": "Capa 3 (OCR Local - Tesseract)",
                    "requiere_revision_manual": False
                }
            # Capa 4: Gemini Visión Multimodal
            print("    [!] Capa 3 insuficiente. Escalando a Capa 4 de Emergencia (Gemini Visión)...")
            doc_recortado = fitz.open()
            for idx in indices_objetivo:
                doc_recortado.insert_pdf(doc_fitz, from_page=idx, to_page=idx)
            bytes_recortados_c4 = doc_recortado.write()
            doc_recortado.close()
            doc_fitz.close()
            return {
                "modo_vision_multimodal": True,
                "contenido_payload": bytes_recortados_c4,
                "nombre_archivo": nombre_corto,
                "numero_expediente": expediente,
                "tipo_proceso": f"Capa 4 (Gemini Visión - Mini PDF de {len(indices_objetivo)} pág.)",
                "requiere_revision_manual": False
            }
        except Exception as e:
            if doc_fitz:
                try:
                    doc_fitz.close()
                except Exception:
                    pass
            return {"requiere_revision_manual": True, "motivo": f"Fallo crítico abriendo estructura del PDF: {str(e)}"}
    def ejecutar_extraccion_gemini(
        self,
        contenido_entrada: Any,
        es_archivo_completo: bool = False,
        nombre_archivo: str = "temp.pdf"
    ) -> Dict[str, Any]:
        config_llm = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self.config.json_schema,
            temperature=0.0
        )
        archivo_remoto = None
        try:
            if es_archivo_completo:
                archivo_remoto = self.client.files.upload(
                    file=BytesIO(contenido_entrada),
                    config=types.UploadFileConfig(mime_type="application/pdf", display_name=f"mini_{nombre_archivo}")
                )
                contenidos_llm = [archivo_remoto, self.config.prompt_extraccion]
            else:
                contenidos_llm = [contenido_entrada, self.config.prompt_extraccion]
            max_intentos = 3
            for intento in range(1, max_intentos + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.config.model_name,
                        contents=contenidos_llm,
                        config=config_llm
                    )
                    data_raw = json.loads(response.text)
                    # Validación Pydantic encapsulada en el contrato
                    registro_datos, campos_faltantes = self.config.validar_y_estructurar(data_raw)
                    return {
                        "datos_extraidos": registro_datos,
                        "campos_faltantes": campos_faltantes,
                        "completado_exitosamente": len(campos_faltantes) == 0,
                        "error": None
                    }
                except APIError as e:
                    if e.code == 429 and intento < max_intentos:
                        time.sleep(20 + (intento * 3))
                    else:
                        return {
                            "datos_extraidos": {},
                            "campos_faltantes": self.config.campos_requeridos,
                            "completado_exitosamente": False,
                            "error": e.message
                        }
        except Exception as e:
            return {
                "datos_extraidos": {},
                "campos_faltantes": self.config.campos_requeridos,
                "completado_exitosamente": False,
                "error": str(e)
            }
        finally:
            if archivo_remoto:
                try:
                    self.client.files.delete(name=archivo_remoto.name)
                except Exception:
                    pass
    def _procesar_carpeta_local(self):
        archivos = [
            f for f in os.listdir(self.carpeta_base)
            if os.path.isfile(os.path.join(self.carpeta_base, f)) and f.lower().endswith(".pdf")
        ]
        if not archivos:
            print(f"[-] No se encontraron nuevos archivos .pdf en '{self.carpeta_base}'.")
            return
        print(f"[+] Iniciando procesamiento de lote definitivo (4 Capas) para {len(archivos)} archivos...\n")
        for nombre_archivo in archivos:
            self.reporte_final["total_processed"] += 1
            ruta_completa_pdf = os.path.join(self.carpeta_base, nombre_archivo)
            print(f"[Analizando archivo] -> {nombre_archivo}")
            try:
                # IMPORTANTE: el plugin se selecciona para cada PDF antes de extraer.
                self._seleccionar_configuracion_documento(ruta_completa_pdf)
            except Exception as exc:
                nombre_salida_json = os.path.splitext(nombre_archivo)[0] + "_resultado.json"
                resultado_error = {
                    "archivo_origen": nombre_archivo,
                    "requiere_revision_manual": True,
                    "motivo": f"No se pudo seleccionar/validar el plugin: {exc}",
                    "datos_extraidos": {},
                    "campos_faltantes": [],
                    "completado_exitosamente": False,
                }
                ruta_json = os.path.join(self.carpeta_revision, nombre_salida_json)
                if os.path.exists(ruta_json):
                    base_json, extension_json = os.path.splitext(nombre_salida_json)
                    contador_json = 1
                    while os.path.exists(ruta_json):
                        ruta_json = os.path.join(
                            self.carpeta_revision,
                            f"{base_json}_{contador_json}{extension_json}",
                        )
                        contador_json += 1
                with open(ruta_json, "w", encoding="utf-8") as archivo_json:
                    json.dump(resultado_error, archivo_json, indent=2, ensure_ascii=False)
                destino_pdf = self._mover_pdf_a_revision(ruta_completa_pdf, nombre_archivo)
                self.reporte_final["enviados_a_revision_manual"] += 1
                self.reporte_final["detalles_lote"].append({
                    "archivo": nombre_archivo,
                    "estado": "Revisión manual: fallo de selección del plugin",
                    "motivo": str(exc),
                    "json": ruta_json,
                    "pdf_movido_a": destino_pdf,
                })
                print(f"    [→ REVISIÓN MANUAL] {exc}")
                continue
            resultado_lectura = self.verificar_y_filtrar_pdf(ruta_completa_pdf)
            nombre_salida_json = os.path.splitext(nombre_archivo)[0] + "_resultado.json"
            if resultado_lectura.get("requiere_revision_manual"):
                self.reporte_final["enviados_a_revision_manual"] += 1
                with open(os.path.join(self.carpeta_revision, nombre_salida_json), 'w', encoding='utf-8') as f_json:
                    json.dump(resultado_lectura, f_json, indent=2, ensure_ascii=False)
                self._mover_pdf_a_revision(ruta_completa_pdf, nombre_archivo)
                print(f"    [→ AISLADO] Movido por: {resultado_lectura.get('motivo')}\n")
                continue
            es_multimodal = resultado_lectura["modo_vision_multimodal"]
            tipo_proceso = resultado_lectura["tipo_proceso"]
            if es_multimodal:
                print(f"    [✓ {tipo_proceso}] Subiendo fragmento recortado binario a Gemini Visión...")
                entrada_llm = resultado_lectura["contenido_payload"]
                resultado_ia = self.ejecutar_extraccion_gemini(
                    entrada_llm,
                    es_archivo_completo=True,
                    nombre_archivo=resultado_lectura["nombre_archivo"]
                )
            else:
                print(f"    [✓ {tipo_proceso}] Enviando texto plano estructurado...")
                entrada_llm = resultado_lectura["contenido_payload"]
                resultado_ia = self.ejecutar_extraccion_gemini(entrada_llm, es_archivo_completo=False)
            if resultado_ia.get("error"):
                self.reporte_final["enviados_a_revision_manual"] += 1
                resultado_lectura["requiere_revision_manual"] = True
                resultado_lectura["motivo"] = f"Error API Gemini: {resultado_ia['error']}"
                # FIX: Remover o reemplazar el buffer binario antes de guardar en JSON
                if isinstance(resultado_lectura.get("contenido_payload"), bytes):
                    resultado_lectura["contenido_payload"] = "<buffer_pdf_binario>"
                with open(os.path.join(self.carpeta_revision, nombre_salida_json), 'w', encoding='utf-8') as f_json:
                    json.dump(resultado_lectura, f_json, indent=2, ensure_ascii=False)
                self._mover_pdf_a_revision(ruta_completa_pdf, nombre_archivo)
                print(f"    [→ AISLADO] PDF movido por error de API.\n")
                continue
            datos_extraidos = resultado_ia.get("datos_extraidos", {})
            tiene_faltantes = len(resultado_ia.get("campos_faltantes", [])) > 0
            estado_final_str = f"{tipo_proceso} - " + ("Con campos faltantes" if tiene_faltantes else "Completado al 100%")
            if tiene_faltantes:
                self.reporte_final["con_campos_faltantes"] += 1
            else:
                self.reporte_final["exitosos_completos"] += 1
            expediente_final = datos_extraidos.get("numero_expediente") or resultado_lectura.get("numero_expediente")
            resultado_final = {
                "archivo_origen": nombre_archivo,
                "numero_expediente": expediente_final,
                "pipeline_origen": tipo_proceso,
                "requiere_revision_manual": tiene_faltantes,
                "datos_extraidos": datos_extraidos,
                "campos_faltantes": resultado_ia.get("campos_faltantes", []),
                "completado_exitosamente": resultado_ia.get("completado_exitosamente", False)
            }
            with open(os.path.join(self.carpeta_base, nombre_salida_json), 'w', encoding='utf-8') as f_json:
                json.dump(resultado_final, f_json, indent=2, ensure_ascii=False)
            print(f"    [Éxito] JSON generado: {nombre_salida_json}")
            print(f"            Origen Proceso: {estado_final_str}\n")
            self.reporte_final["detalles_lote"].append({
                "archivo": nombre_archivo,
                "estado": estado_final_str,
                "campos_faltantes": resultado_ia.get("campos_faltantes", [])
            })
            time.sleep(2)
        with open(os.path.join(self.carpeta_base, "reporte_consolidado.json"), 'w', encoding='utf-8') as f_rep:
            json.dump(self.reporte_final, f_rep, indent=2, ensure_ascii=False)
        print("[+++ LOTE FINALIZADO +++] Reporte consolidado guardado con éxito.")
    def procesar_carpeta_local(self):
        """Ejecuta el lote y guarda siempre el reporte consolidado, incluso ante errores."""
        try:
            self._procesar_carpeta_local()
        finally:
            ruta_reporte = os.path.join(self.carpeta_base, "reporte_consolidado.json")
            with open(ruta_reporte, "w", encoding="utf-8") as archivo_reporte:
                json.dump(self.reporte_final, archivo_reporte, indent=2, ensure_ascii=False)
            print(f"[Reporte] Guardado en: {ruta_reporte}")
    def procesar_pdf_desde_bytes(self, pdf_bytes: bytes, nombre_archivo: str) -> Dict[str, Any]:
        """
        Permite procesar un PDF provisto externamente en formato de bytes (streams),
        aplicando la selección de plugin, filtrado por capas y extracción con Gemini.
        """
        import tempfile
        doc_fitz = None
        try:
            doc_fitz = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_paginas = len(doc_fitz)
            
            if total_paginas == 0:
                doc_fitz.close()
                return {"requiere_revision_manual": True, "motivo": "El stream PDF no contiene páginas."}

            # Seleccionar configuración usando la primera página de muestra
            texto_muestra = doc_fitz[0].get_text() or ""
            if not texto_muestra:
                texto_muestra = self.ejecutar_pipeline_capa3(doc_fitz, [0]).strip()
            
            # Autodetección o asignación de configuración mediante el factory
            if self.factory and not self.config:
                selector = getattr(self.factory, "autodetectar_configuracion", None)
                if selector:
                    self.config = selector(texto_muestra)
                    if self.config:
                        self.json_schema = self.config.json_schema
                        self.palabras_clave = list(self.config.palabras_clave)

            doc_fitz.close()

            # Guardar temporalmente en archivo seguro para reutilizar el pipeline de capas existente
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = temp_file.name

            try:
                resultado_filtrado = self.verificar_y_filtrar_pdf(temp_path)
                return resultado_filtrado
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

        except Exception as e:
            if doc_fitz:
                try:
                    doc_fitz.close()
                except Exception:
                    pass
            return {"requiere_revision_manual": True, "motivo": f"Fallo procesando stream de bytes: {str(e)}"}

if __name__ == "__main__":
    RUTA_CARPETA = r"D:\libs\chaskiwasi_simple\mis_pdfs_legales"
    factory = ConfigurationFactory()
    if not factory.claves_disponibles:
        raise RuntimeError(
            "No se cargaron plugins del grupo 'chaskiwasi.plugins'. "
            "Verifica la instalación del plugin y sus entry points."
        )
    procesador = ExtractorDocumentalUniversal(
        config=None,
        carpeta_base=RUTA_CARPETA,
        factory=factory,
    )
    procesador.procesar_carpeta_local()
