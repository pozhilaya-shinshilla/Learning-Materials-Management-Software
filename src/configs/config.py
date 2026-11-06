from src.domain.enums import FileType

ALLOWED_FILE_TYPES: frozenset[FileType] = frozenset(
    {
        FileType.PDF,
        FileType.DOCX,
        FileType.PPTX,
        FileType.XLSX,
        FileType.JPG,
        FileType.PNG,
    }
)

MAX_FILE_SIZE_BYTES: int = 100 * 1024 * 1024

RESET_TOKEN_TTL_MINUTES: int = 30

# Сколько часов действует токен доступа к API, выданный при входе.
AUTH_TOKEN_TTL_HOURS: int = 12

# Сколько последних правок каждого материала можно отменить.
MAX_REVISIONS_PER_MATERIAL: int = 20
