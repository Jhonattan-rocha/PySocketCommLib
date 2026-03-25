from abc import ABC, abstractmethod
from typing import Optional, List, Any


class BaseField(ABC):
    """
    Classe base para todos os campos do ORM.

    Parâmetros comuns:
        db_column_name  Nome da coluna no banco (default: nome do atributo na classe).
        primary_key     Define como chave primária.
        nullable        Permite NULL (default: True).
        unique          Adiciona restrição UNIQUE.
        default         Valor padrão (Python) para novos registros.
        index           Marca para criação de índice (registrado no schema).
        choices         Lista de valores válidos — validado em validate().
    """

    def __init__(
        self,
        db_column_name: Optional[str] = None,
        primary_key: bool = False,
        nullable: bool = True,
        unique: bool = False,
        default: Any = None,
        index: bool = False,
        choices: Optional[List[Any]] = None,
    ):
        self.db_column_name = db_column_name
        self.primary_key = primary_key
        self.nullable = nullable
        self.unique = unique
        self.default = default
        self.index = index
        self.choices = choices

    @abstractmethod
    def get_sql_type(self) -> str:
        """Retorna o tipo SQL genérico do campo (mapeado pelo dialeto)."""
        pass

    def validate(self, value: Any) -> None:
        """
        Valida o valor antes do INSERT/UPDATE.
        Subclasses devem chamar super().validate(value) para manter as verificações base.
        Levanta ValueError se inválido.
        """
        if not self.nullable and value is None:
            raise ValueError(
                f"Campo '{self.db_column_name or '<unnamed>'}' não pode ser NULL."
            )
        if self.choices is not None and value is not None and value not in self.choices:
            raise ValueError(
                f"Valor '{value}' inválido. Opções: {self.choices}"
            )


# ---------------------------------------------------------------------------
# Inteiros
# ---------------------------------------------------------------------------

class IntegerField(BaseField):
    """INTEGER — inteiro de precisão padrão."""
    def get_sql_type(self) -> str:
        return "INTEGER"


class SmallIntegerField(BaseField):
    """SMALLINT — inteiro de 2 bytes (-32 768 a 32 767)."""
    def get_sql_type(self) -> str:
        return "SMALLINT"


class BigIntegerField(BaseField):
    """BIGINT — inteiro de 8 bytes."""
    def get_sql_type(self) -> str:
        return "BIGINT"


class AutoField(BaseField):
    """
    Campo auto-incremento para chave primária.

    Mapeia para:
        PostgreSQL  → SERIAL
        MySQL       → INT AUTO_INCREMENT
        SQLite      → INTEGER (AUTOINCREMENT via PRIMARY KEY)
    """
    def __init__(self, **kwargs):
        kwargs.setdefault('primary_key', True)
        kwargs.setdefault('nullable', False)
        super().__init__(**kwargs)

    def get_sql_type(self) -> str:
        return "AUTOFIELD"  # dialeto mapeia para o tipo correto


class PositiveIntegerField(IntegerField):
    """INTEGER com validação Python de valor >= 0."""
    def validate(self, value: Any) -> None:
        super().validate(value)
        if value is not None and value < 0:
            raise ValueError(
                f"PositiveIntegerField não aceita valores negativos: {value}"
            )


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------

class TextField(BaseField):
    """TEXT — string sem limite de comprimento."""
    def get_sql_type(self) -> str:
        return "TEXT"


class CharField(BaseField):
    """VARCHAR(max_length) — string com comprimento máximo."""

    def __init__(self, max_length: int = 255, **kwargs):
        super().__init__(**kwargs)
        if max_length <= 0:
            raise ValueError("max_length deve ser um inteiro positivo.")
        self.max_length = max_length

    def get_sql_type(self) -> str:
        return f"VARCHAR({self.max_length})"

    def validate(self, value: Any) -> None:
        super().validate(value)
        if value is not None and len(str(value)) > self.max_length:
            raise ValueError(
                f"Valor excede o comprimento máximo de {self.max_length}: '{value}'"
            )


# ---------------------------------------------------------------------------
# Numéricos
# ---------------------------------------------------------------------------

class FloatField(BaseField):
    """REAL / FLOAT — número de ponto flutuante."""
    def get_sql_type(self) -> str:
        return "REAL"


class DecimalField(BaseField):
    """DECIMAL — número de precisão exata."""
    def get_sql_type(self) -> str:
        return "DECIMAL"


# ---------------------------------------------------------------------------
# Booleano
# ---------------------------------------------------------------------------

class BooleanField(BaseField):
    """BOOLEAN — armazenado como TINYINT(1) no MySQL, INTEGER no SQLite."""
    def get_sql_type(self) -> str:
        return "BOOLEAN"

    def validate(self, value: Any) -> None:
        super().validate(value)
        if value is not None and not isinstance(value, (bool, int)):
            raise ValueError(f"BooleanField espera True/False/0/1, recebeu: {value!r}")


# ---------------------------------------------------------------------------
# Data e hora
# ---------------------------------------------------------------------------

class DateTimeField(BaseField):
    """
    TIMESTAMP — data e hora.

    Parâmetros extras:
        auto_now_add  Preenche automaticamente com datetime.now() no INSERT.
        auto_now      Atualiza automaticamente com datetime.now() em cada SAVE.
    """

    def __init__(
        self,
        auto_now_add: bool = False,
        auto_now: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.auto_now_add = auto_now_add
        self.auto_now = auto_now
        # Campos auto gerenciados são implicitamente nullable=True em Python
        if auto_now_add or auto_now:
            self.nullable = True

    def get_sql_type(self) -> str:
        return "TIMESTAMP"


# ---------------------------------------------------------------------------
# Dados estruturados
# ---------------------------------------------------------------------------

class JSONField(BaseField):
    """JSONB (PostgreSQL) / TEXT (outros) — dados semi-estruturados."""
    def get_sql_type(self) -> str:
        return "JSONB"


class UUIDField(BaseField):
    """UUID — identificador único universal."""
    def get_sql_type(self) -> str:
        return "UUID"


class BinaryField(BaseField):
    """
    Dados binários.

    Mapeia para:
        PostgreSQL  → BYTEA
        MySQL       → BLOB
        SQLite      → BLOB
    """
    def get_sql_type(self) -> str:
        return "BINARY"


# ---------------------------------------------------------------------------
# Enum / choices
# ---------------------------------------------------------------------------

class EnumField(BaseField):
    """
    Campo TEXT com validação de choices.

    Exemplo::

        status = EnumField(choices=["active", "inactive", "pending"])
    """

    def __init__(self, choices: List[Any], **kwargs):
        if not choices:
            raise ValueError("EnumField requer ao menos uma opção em choices.")
        kwargs['choices'] = choices
        super().__init__(**kwargs)

    def get_sql_type(self) -> str:
        return "TEXT"


# ---------------------------------------------------------------------------
# Chave estrangeira
# ---------------------------------------------------------------------------

class ForeignKeyField(BaseField):
    """
    Chave estrangeira para outra tabela.

    Parâmetros extras:
        reference_table   Nome da tabela referenciada.
        reference_column  Coluna referenciada (default: "id").
        on_delete         Ação ON DELETE (default: "CASCADE").
        on_update         Ação ON UPDATE (default: "CASCADE").
        to_model          Classe BaseModel para uso em select_related().
    """

    def __init__(
        self,
        reference_table: str,
        reference_column: str = "id",
        on_delete: str = "CASCADE",
        on_update: str = "CASCADE",
        to_model=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.reference_table = reference_table
        self.reference_column = reference_column
        self.on_delete = on_delete
        self.on_update = on_update
        self.to_model = to_model

    def get_sql_type(self) -> str:
        return "INTEGER"

    def get_foreign_key_clause(self, column_name: str) -> str:
        return (
            f'FOREIGN KEY ("{column_name}") '
            f'REFERENCES "{self.reference_table}"("{self.reference_column}") '
            f'ON DELETE {self.on_delete} ON UPDATE {self.on_update}'
        )
