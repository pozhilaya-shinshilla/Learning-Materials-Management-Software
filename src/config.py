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
