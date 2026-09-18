# tests/conftest.py
import os
import pytest
import enum
from chaskiwasi.config.taxonomy_registry import TaxonomyRegistry


# 1. Definimos Enums falsos mínimos para que los tests pasen
class MockSourceEnum(enum.Enum):
    SUNARP = "SUNARP"
    REMAJU = "REMAJU"

class MockSectionEnum(enum.Enum):
    ENCABEZADO = "ENCABEZADO"
    RESOLUCION = "RESOLUCION"
    PARTES = "PARTES"
    GRAVAMEN = "GRAVAMEN"

# 2. Inyectamos las taxonomías globales ANTES de que los tests importen las clases reales
TaxonomyRegistry.inject_taxonomies(MockSourceEnum, MockSectionEnum)


@pytest.fixture(autouse=True)
def mock_mandatory_environment_variables(monkeypatch):
    """
    Fixture global automático que intercepta cada test del repositorio inyectando 
    las credenciales obligatorias de QuipuSettings y GoogleDrivePublisher,
    blindando el aislamiento de RAM y red en la PC de la oficina.
    """
    # Clave privada dummy estructurada en formato PEM legítimo para engañar a la librería de criptografía de Google
    mock_pem_key = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Xo/yC1V6D4k...\n"
        "-----END RSA PRIVATE KEY-----\n"
    )
    
    monkeypatch.setenv("NESTJS_API_URL", "http://localhost:3000/api")
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "mock_folder_id_123")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMockKey_Global_777")
    monkeypatch.setenv("GOOGLE_CLIENT_EMAIL", "mock-service-account@://gserviceaccount.com")
    monkeypatch.setenv("GOOGLE_PRIVATE_KEY", mock_pem_key)
    monkeypatch.setenv("QUIPU_API_AUTH_TOKEN", "TokenSecretoTest123")
