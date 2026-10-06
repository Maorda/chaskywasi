# Contrato de plugins — Chaskiwasi 0.3.0

## 1. Principio

Chaskiwasi es el motor documental y RAG. Un plugin configura el motor para un dominio de negocio y es dueño de su taxonomía, reglas de clasificación, reglas de consulta y extracción semántica.

El core no conoce dominios concretos como REMAJU, SUNARP, CEJ, ingeniería u otros.

## 2. Entry point único

Los plugins se publican en el grupo:

```text
chaskiwasi.plugins
```

El entry point debe cargar una función sin argumentos que devuelva una instancia de `PluginDefinition`.

Ejemplo conceptual:

```text
[project.entry-points."chaskiwasi.plugins"]
mi_plugin = "mi_paquete.plugin:create_plugin"
```

El nombre del entry point debe coincidir con `PluginDefinition.name`.

## 3. PluginDefinition

Un plugin puede aportar:

- `name`: identificador único.
- `taxonomy`: taxonomía exclusiva del plugin.
- `strategy_factory(context)`: estrategias ordenadas para `CascadeFactory`.
- `query_rules_factory()`: reglas de intención para `CrossQueryFilter`.
- `extractor(context)`: extracción específica del negocio a JSON.
- `metadata`: información adicional del plugin.

Todos los componentes son opcionales excepto `name`, `taxonomy` y `strategy_factory`.

## 4. Taxonomía

No existe una taxonomía global de dominio.

Cada plugin define sus propios:

- `SourceEnum`
- `SectionEnum`
- `Taxonomy`

El core mantiene el registro activo mediante `TaxonomyRegistry` y entrega la taxonomía al plugin mediante `PluginContext` y `ClassificationContext`.

## 5. Clasificación

`CascadeFactory` es el motor central.

El plugin solamente proporciona las estrategias y su orden. Las estrategias reciben un `ClassificationContext` controlado por el core.

Flujo:

```text
PluginDefinition
      ↓
PluginRegistry
      ↓
PluginContext
      ↓
CascadeFactory
      ↓
Strategy 1 → Strategy 2 → ... → Strategy N
```

Las estrategias no descubren plugins ni consultan registros globales.

## 6. Documento

El flujo documental del core es:

```text
Documento
   ↓
Docling
   ↓
Markdown estructural
   ↓
ChunkTokenizer
   ↓
chunks de 256 tokens
   ↓
CascadeFactory
   ↓
clasificación por chunk
   ↓
ChromaDB
   ↓
RAG
```

El extractor del plugin recibe el `ExtractionContext` normalizado y produce el JSON específico del negocio.

## 7. RAG

Chaskiwasi es propietario de la persistencia y consulta RAG.

`ChromaPersistentManager`:

- persiste chunks;
- conserva `id_documento`;
- conserva `fuente`;
- conserva `tipo_seccion`;
- conserva `plugin` cuando corresponde;
- utiliza `upsert` para permitir procesamiento idempotente.

`RagQueryEngine` realiza la recuperación semántica.

`CrossQueryFilter` compone filtros de documento, plugin e intención declarados por los plugins.

## 8. LLM

Las estrategias deterministas y contextuales tienen prioridad. El LLM es último recurso para clasificación.

Gemini es opcional y recibe únicamente el contexto mínimo necesario para clasificación. El core no garantiza cuotas gratuitas de ningún proveedor externo.

## 9. Independencia

`chaskiwasi` no depende de:

- `chaskitambo`;
- `quipu`;
- `chaskiwasi-plugin-remaju`;
- cualquier otro plugin de dominio.

El sentido de dependencia es:

```text
Plugin → Chaskiwasi
Chaskitambo → Chaskiwasi
Quipu → independiente
```

Nunca:

```text
Chaskiwasi → Plugin
Chaskiwasi → Chaskitambo
Chaskiwasi → Quipu
```

## 10. Implementación de referencia

El contrato debe probarse con un plugin externo independiente. El repositorio de `chaskiwasi` no incorpora plugins de dominio: esto garantiza que el core permanezca desacoplado y que cada plugin pueda publicarse y versionarse por separado.
