"""Punto de entrada de ejecución del motor Chaskiwasi.

El trigger solo orquesta el core. No conoce Chaskitambo, Quipu ni ningún dominio.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from chaskiwasi.consolidation.consolidator import ChaskyConsolidator
from chaskiwasi.plugins.registry import PluginRegistry


class ChaskiwasiTrigger:
    """Ejecuta procesamiento documental mediante un plugin de Chaskiwasi."""

    def __init__(self, output_dir: str | Path = "./reportes_maestros") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def process_file(
        self,
        global_id: str,
        plugin_name: str,
        file_path: str | Path,
        output_json_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"El archivo especificado no existe: {path}")
        return await asyncio.to_thread(
            self.process_bytes,
            global_id,
            plugin_name,
            path.read_bytes(),
            output_json_path,
            path.stem,
        )

    async def process_bytes(
        self,
        global_id: str,
        plugin_name: str,
        pdf_bytes: bytes,
        output_json_path: Optional[str | Path] = None,
        source_label: str = "documento",
    ) -> Dict[str, Any]:
        if not pdf_bytes:
            raise ValueError("pdf_bytes no puede estar vacío.")

        PluginRegistry.get(plugin_name)
        output_path = (
            Path(output_json_path)
            if output_json_path is not None
            else self.output_dir / f"master_{global_id}.json"
        )

        consolidator = ChaskyConsolidator()
        return await asyncio.to_thread(
            consolidator.build_master_expediente,
            global_id=global_id,
            data_sources={source_label: pdf_bytes},
            output_json_path=output_path,
            plugin_name=plugin_name,
        )

    async def process_files(
        self,
        global_id: str,
        plugin_name: str,
        files: Dict[str, str | Path],
        output_json_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        PluginRegistry.get(plugin_name)
        data_sources: Dict[str, bytes] = {}
        for source_label, file_path in files.items():
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"El archivo especificado no existe: {path}")
            data_sources[source_label] = path.read_bytes()

        output_path = (
            Path(output_json_path)
            if output_json_path is not None
            else self.output_dir / f"master_{global_id}.json"
        )
        consolidator = ChaskyConsolidator()
        return await asyncio.to_thread(
            consolidator.build_master_expediente,
            global_id=global_id,
            data_sources=data_sources,
            output_json_path=output_path,
            plugin_name=plugin_name,
        )
