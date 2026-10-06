# Chaskiwasi

`chaskiwasi` es el motor documental y RAG local sobre el que se construyen plugins de dominio.

## Responsabilidad

Chaskiwasi es responsable de:

- ingestión documental mediante Docling;
- conversión a Markdown estructural;
- fragmentación de 256 tokens mediante `tiktoken`;
- clasificación mediante `CascadeFactory`;
- registro y ejecución de plugins;
- extracción estructurada delegada al plugin;
- persistencia RAG en ChromaDB;
- recuperación semántica;
- filtros de consulta declarados por plugins.

Chaskiwasi **no conoce ningún dominio de negocio concreto**.

## Arquitectura

```text
Documento
   │
   ▼
Docling
   │
   ▼
Markdown estructural
   │
   ▼
ChunkTokenizer (256 tokens)
   │
   ▼
CascadeFactory
   │
   ├── estrategias deterministas
   ├── contexto
   └── LLM opcional como último recurso
   │
   ├───────────────┐
   ▼               ▼
Extractor       ChromaDB
(plugin)          (RAG)
   │               │
   ▼               ▼
 JSON          RagQueryEngine
```

## Plugins

Un plugin es un paquete independiente que implementa `PluginDefinition` y se publica mediante el entry point:

```text
chaskiwasi.plugins
```

El plugin aporta:

- su propia taxonomía;
- sus estrategias de clasificación;
- sus reglas de intención;
- su extractor estructurado opcional.

El core mantiene el registro y proporciona el contexto controlado.

## Dependencias

Las versiones mínimas están declaradas en `pyproject.toml` y ese archivo es la fuente de verdad.

Gemini es opcional:

```bash
pip install "chaskiwasi[gemini]"
```

El diseño prioriza clasificación determinista/contextual y deja el LLM como último recurso para reducir consumo de tokens y memoria.

## Instalación

```bash
python -m pip install .
```

Para desarrollo:

```bash
python -m pip install -e ".[dev]"
```

## CLI

Listar plugins instalados:

```bash
chaskiwasi list
```

Procesar un PDF:

```bash
chaskiwasi ingesta pdf documento.pdf --plugin NOMBRE_PLUGIN
```

Consultar la configuración de persistencia vectorial:

```bash
chaskiwasi vector status
```

## Contrato

El contrato completo de plugins está documentado en:

`docs/architecture/PLUGIN_CONTRACT_0.3.0.md`

## Independencia

La dirección de dependencias es:

```text
Plugin ──────────► Chaskiwasi
Chaskitambo ─────► Chaskiwasi
Quipu ───────────► independiente
```

Nunca:

```text
Chaskiwasi ──► Plugin de dominio
Chaskiwasi ──► Chaskitambo
Chaskiwasi ──► Quipu
```
