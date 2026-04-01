import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime
from ..cache import MemoryCache
from ..abstracts.field_types import BaseField, ForeignKeyField, DateTimeField
from ..abstracts.dialetecs import SQLDialect
from ..abstracts.connection_types import Connection
from ..querys.page import Page
from ...exceptions import ConnectionError as OrmConnectionError, ValidationError
from typing import Tuple, Dict, List, Any, Optional, Generator

logger = logging.getLogger(__name__)


class BaseModel:
    """
    Base class for database models.
    Provides ORM-like functionality for interacting with databases.
    """
    dialect: SQLDialect = None  # Dialect to be set by concrete models
    connection: Connection = None  # Connection instance to be set
    _cache = MemoryCache()

    # Registry of all concrete BaseModel subclasses, used by makemigrations.
    _registry: List[type] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Only register concrete subclasses (skip abstract intermediaries that
        # leave dialect/connection as None and don't define __tablename__).
        BaseModel._registry.append(cls)

    @classmethod
    def build_where_clause(cls, conditions: dict, param_offset: int = 0) -> Tuple[str, tuple]:
        """
        Constrói uma cláusula WHERE parametrizada, segura contra SQL injection.

        param_offset — desloca a numeração dos placeholders PostgreSQL ($N).
        Use param_offset=len(data) ao combinar com SET params em UPDATE.

        Retorna uma tupla (cláusula_sql, params) onde os valores nunca são
        interpolados diretamente na string SQL.
        """
        clause_parts = []
        params = []

        # O placeholder depende do dialeto
        def placeholder(index: int) -> str:
            if cls.dialect is None:
                return "?"
            dialect_name = type(cls.dialect).__name__.lower()
            if "postgres" in dialect_name or "psql" in dialect_name:
                return f"${index + param_offset}"
            if "mysql" in dialect_name:
                return "%s"
            return "?"

        param_index = 1
        for key, value in conditions.items():
            if "__" in key:
                field, op = key.split("__", 1)
            else:
                field, op = key, "eq"

            column = f'"{field}"'

            if op == "eq":
                clause_parts.append(f"{column} = {placeholder(param_index)}")
                params.append(value)
                param_index += 1
            elif op == "lt":
                clause_parts.append(f"{column} < {placeholder(param_index)}")
                params.append(value)
                param_index += 1
            elif op == "lte":
                clause_parts.append(f"{column} <= {placeholder(param_index)}")
                params.append(value)
                param_index += 1
            elif op == "gt":
                clause_parts.append(f"{column} > {placeholder(param_index)}")
                params.append(value)
                param_index += 1
            elif op == "gte":
                clause_parts.append(f"{column} >= {placeholder(param_index)}")
                params.append(value)
                param_index += 1
            elif op == "like":
                clause_parts.append(f"{column} LIKE {placeholder(param_index)}")
                params.append(f"%{value}%")
                param_index += 1
            elif op == "in":
                if not value:
                    raise ValueError("Operador 'in' requer uma lista não vazia")
                placeholders = ", ".join(placeholder(param_index + i) for i in range(len(value)))
                clause_parts.append(f"{column} IN ({placeholders})")
                params.extend(value)
                param_index += len(value)
            else:
                raise ValueError(f"Operador não suportado: {op}")

        return " AND ".join(clause_parts), tuple(params)

    @classmethod
    def filter(cls, **conditions):
        where_clause, params = cls.build_where_clause(conditions)
        return cls.select(where_condition=where_clause, where_params=params)

    @classmethod
    def filter_delete(cls, **conditions):
        """
        Deleta registros que correspondem às condições — type-safe, sem SQL cru.

        Exemplo::

            User.filter_delete(status__eq="inactive")
        """
        if not conditions:
            raise ValueError("filter_delete requer ao menos uma condição para evitar deleção total.")
        if not cls.connection:
            raise OrmConnectionError("Conexão não definida. Chame set_connection().")
        where_clause, params = cls.build_where_clause(conditions)
        sql = cls.delete_sql(where_clause)
        cls._cache.clear_prefix(cls.get_table_name())
        logger.debug("filter_delete() on %s WHERE %s", cls.get_table_name(), where_clause)
        cls.connection.run(sql, params if params else None)

    @classmethod
    def create(cls, **kwargs) -> 'BaseModel':
        """Cria uma instância, salva no banco e a retorna."""
        instance = cls(**kwargs)
        instance.save()
        return instance

    @classmethod
    def count(cls, **conditions) -> int:
        """Retorna o número de registros que correspondem às condições."""
        if not cls.connection:
            raise OrmConnectionError("Conexão não definida. Chame set_connection().")
        table = cls.dialect.quote_identifier(cls.get_table_name())
        if conditions:
            where, params = cls.build_where_clause(conditions)
            sql = f"SELECT COUNT(*) AS cnt FROM {table} WHERE {where}"
        else:
            sql = f"SELECT COUNT(*) AS cnt FROM {table}"
            params = ()
        result = cls.connection.run(sql, params if params else None)
        return cls._extract_scalar(result, default=0)

    @classmethod
    def exists(cls, **conditions) -> bool:
        """Retorna True se existir ao menos um registro correspondente."""
        return cls.count(**conditions) > 0

    @classmethod
    def paginate(
        cls,
        page: int = 1,
        page_size: int = 20,
        order_by: Optional[List[str]] = None,
        **conditions,
    ) -> Page:
        """
        Retorna uma página de registros com metadados de navegação.

        Args:
            page:      Página atual (começa em 1).
            page_size: Máximo de registros por página.
            order_by:  Lista de colunas para ORDER BY, ex: ``["name ASC", "id DESC"]``.
            **conditions: Filtros iguais aos de ``filter()`` (campo__lookup=valor).

        Returns:
            :class:`~ORM.querys.page.Page` com ``data``, ``total``,
            ``total_pages``, ``has_next``, ``has_prev``.

        Example::

            result = User.paginate(page=2, page_size=10, active=True)
            for user in result.data:
                print(user["name"])
            print(f"{result.page}/{result.total_pages}")
        """
        page = max(1, page)
        page_size = max(1, page_size)
        offset = (page - 1) * page_size

        total = cls.count(**conditions)

        if conditions:
            where, params = cls.build_where_clause(conditions)
            data = cls.select(
                where_condition=where,
                where_params=params,
                order_by=order_by,
                limit=page_size,
                offset=offset,
            )
        else:
            data = cls.select(order_by=order_by, limit=page_size, offset=offset)

        return Page(data=data or [], page=page, page_size=page_size, total=total)

    @classmethod
    async def async_paginate(
        cls,
        page: int = 1,
        page_size: int = 20,
        order_by: Optional[List[str]] = None,
        **conditions,
    ) -> Page:
        """Versão assíncrona de paginate()."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: cls.paginate(page, page_size, order_by, **conditions),
        )

    @classmethod
    def first(cls, **conditions) -> Optional[Dict[str, Any]]:
        """Retorna o primeiro registro correspondente (LIMIT 1)."""
        if conditions:
            where, params = cls.build_where_clause(conditions)
            rows = cls.select(where_condition=where, where_params=params, limit=1)
        else:
            rows = cls.select(limit=1)
        return rows[0] if rows else None

    @classmethod
    def last(cls, **conditions) -> Optional[Dict[str, Any]]:
        """Retorna o último registro por PK (ORDER BY pk DESC LIMIT 1)."""
        if not cls.connection:
            raise OrmConnectionError("Conexão não definida. Chame set_connection().")
        _, pks = cls.get_fields()
        table = cls.dialect.quote_identifier(cls.get_table_name())
        if conditions:
            where, params = cls.build_where_clause(conditions)
            sql = f"SELECT * FROM {table} WHERE {where}"
        else:
            sql = f"SELECT * FROM {table}"
            params = ()
        if pks:
            quoted_pk = cls.dialect.quote_identifier(pks[0])
            sql += f" ORDER BY {quoted_pk} DESC"
        sql += " LIMIT 1"
        result = cls.connection.run(sql, params if params else None)
        if not result:
            return None
        if isinstance(result, list):
            return result[0] if result else None
        return None

    @classmethod
    def bulk_insert(cls, records: List[Dict[str, Any]]) -> None:
        """
        Insere múltiplos registros.

        Cada item da lista deve ser um dict ``{coluna: valor}``.
        Executa um INSERT por registro (para compatibilidade máxima entre dialetos).
        """
        if not records:
            return
        if not cls.connection:
            raise OrmConnectionError("Conexão não definida. Chame set_connection().")
        cls._cache.clear_prefix(cls.get_table_name())
        logger.debug("bulk_insert() %d records into %s", len(records), cls.get_table_name())
        for record in records:
            sql, params = cls.insert_sql(record)
            cls.connection.run(sql, params)

    def refresh(self) -> None:
        """Recarrega os valores desta instância a partir do banco de dados."""
        fields, pks = self.__class__.get_fields()
        if not pks:
            raise ValueError("refresh() requer um campo primary_key definido no modelo.")
        pk_col = pks[0]
        pk_attr = next(
            (attr for attr, f in fields.items() if (f.db_column_name or attr) == pk_col),
            None,
        )
        if pk_attr is None:
            return
        pk_value = getattr(self, pk_attr)
        result = self.__class__.get(**{pk_col: pk_value})
        if result:
            for attr_name, field in fields.items():
                col = field.db_column_name if field.db_column_name else attr_name
                value = result.get(col) if col in result else result.get(attr_name)
                if value is not None:
                    setattr(self, attr_name, value)

    @classmethod
    def _extract_scalar(cls, result, default=None):
        """Extrai o primeiro valor escalar de um resultado de query."""
        if not result:
            return default
        if isinstance(result, list):
            if result and isinstance(result[0], dict):
                return list(result[0].values())[0]
            if result and isinstance(result[0], (list, tuple)):
                return result[0][0]
        if isinstance(result, tuple):  # PostgreSQL driver raw: (rows, cols)
            rows, _ = result
            if rows:
                return rows[0][0]
        return default

    @classmethod
    def filter_update(cls, data: Dict[str, Any], **conditions):
        """
        Atualiza registros que correspondem às condições — type-safe, sem SQL cru.

        Os placeholders WHERE são numerados a partir de len(data)+1 para
        PostgreSQL ($N), garantindo params corretos em: SET $1…$N WHERE $N+1…

        Exemplo::

            User.filter_update({"status": "active"}, id__eq=42)
        """
        if not conditions:
            raise ValueError("filter_update requer ao menos uma condição para evitar atualização total.")
        if not cls.connection:
            raise OrmConnectionError("Conexão não definida. Chame set_connection().")
        where_clause, where_params = cls.build_where_clause(conditions, param_offset=len(data))
        sql, set_params = cls.update_sql(data, where_clause)
        cls._cache.clear_prefix(cls.get_table_name())
        logger.debug("filter_update() on %s WHERE %s", cls.get_table_name(), where_clause)
        cls.connection.run(sql, set_params + where_params)

    @classmethod
    def get(cls, **conditions):
        where, params = cls.build_where_clause(conditions)
        key = f"{cls.get_table_name()}|{where}|{params}"
        cached = cls._cache.get(key)
        if cached:
            return cached
        result = cls.select(where_condition=where, where_params=params, limit=1)
        if result:
            cls._cache.set(key, result[0])
            return result[0]
        return None

    @classmethod
    def set_connection(cls, connection: Connection):
        """Sets the connection to be used by the model."""
        cls.connection = connection
        cls.dialect = connection.dialect

    @classmethod
    @contextmanager
    def transaction(cls) -> Generator[None, None, None]:
        """
        Context manager for atomic model operations.

        Usage::

            with MyModel.transaction():
                MyModel.create(name="Alice")
                MyModel.create(name="Bob")
            # auto-commit on success, auto-rollback on exception
        """
        if cls.connection is None:
            raise OrmConnectionError("No database connection set. Call set_connection() on the BaseModel subclass.")
        with cls.connection.transaction():
            yield

    @classmethod
    def get_table_name(cls):
        """Converts class name to snake_case for table name."""
        name = cls.__name__
        return ''.join(['_'+c.lower() if c.isupper() else c for c in name]).lstrip('_')

    @classmethod
    def get_fields(cls) -> Tuple[Dict[str, 'BaseField'], List[str]]:
        """Returns a dictionary of fields defined in the model and a list of primary key column names."""
        fields = {}
        primary_keys = []
        for name, field in cls.__dict__.items():
            if isinstance(field, BaseField):
                fields[name] = field
                db_column_name = field.db_column_name if field.db_column_name else name
                if field.primary_key:
                    primary_keys.append(db_column_name)
        return fields, primary_keys

    @classmethod
    def create_table_sql(cls) -> str:
        """Generates CREATE TABLE SQL based on model fields and dialect."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")

        table_name = cls.get_table_name()
        fields, primary_keys = cls.get_fields()
        return cls.dialect.create_table(table_name, fields, primary_keys)

    @classmethod
    def create_table(cls):
        """Creates the table in the database."""
        if not cls.connection:
            raise OrmConnectionError("No database connection set. Call set_connection() on the BaseModel subclass.")
        sql = cls.create_table_sql()
        cls.connection.run(sql)

    def __init__(self, **kwargs):
        """Initializes a model instance with provided keyword arguments."""
        fields, _ = self.__class__.get_fields()
        for name, field in fields.items():
            db_column_name = field.db_column_name if field.db_column_name else name
            if name in kwargs:
                setattr(self, name, kwargs[name])
            elif db_column_name in kwargs:
                setattr(self, name, kwargs[db_column_name])
            else:
                setattr(self, name, field.default)

        self._data = {}

    def clear_cache(self):
        self._cache.clear_prefix(self.get_table_name())

    @classmethod
    def insert_sql(cls, data: Dict[str, Any]) -> Tuple[str, tuple]:
        """Generates INSERT SQL and parameters for the model."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")
        table_name = cls.get_table_name()
        return cls.dialect.insert(table_name, data)

    def save(self):
        """Saves (inserts) the model instance to the database, running field validation."""
        self.clear_cache()
        if not self.__class__.connection:
            raise OrmConnectionError("No database connection set. Call set_connection() on the BaseModel subclass.")

        fields, primary_keys = self.__class__.get_fields()
        data_to_insert = {}
        for name, field in fields.items():
            db_column_name = field.db_column_name if field.db_column_name else name

            # auto_now / auto_now_add handling
            if isinstance(field, DateTimeField):
                if field.auto_now:
                    setattr(self, name, datetime.now())
                elif field.auto_now_add and getattr(self, name) is None:
                    setattr(self, name, datetime.now())

            value = getattr(self, name)
            field.validate(value)
            data_to_insert[db_column_name] = value

        sql, params = self.__class__.insert_sql(data_to_insert)
        logger.debug("save() INSERT on %s", self.__class__.get_table_name())
        self.__class__.connection.run(sql, params)

    @classmethod
    def delete_sql(cls, where_condition: str) -> str:
        """Generates DELETE SQL for the model."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")
        table_name = cls.get_table_name()
        return cls.dialect.delete(table_name, where_condition)

    @classmethod
    def delete(cls, where_condition: str):
        """Deletes records based on a WHERE condition."""
        if not cls.connection:
            raise OrmConnectionError("No database connection set. Call set_connection() on the BaseModel subclass.")
        sql = cls.delete_sql(where_condition)
        cls.connection.run(sql)

    @classmethod
    def update_sql(cls, data: Dict[str, Any], where_condition: str) -> Tuple[str, tuple]:
        """Generates UPDATE SQL and parameters for the model."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")
        table_name = cls.get_table_name()
        return cls.dialect.update(table_name, data, where_condition)

    @classmethod
    def update(cls, data: Dict[str, Any], where_condition: str):
        """Updates records based on a WHERE condition."""
        cls._cache.clear_prefix(cls.get_table_name())
        if not cls.connection:
            raise OrmConnectionError("No database connection set. Call set_connection() on the BaseModel subclass.")
        sql, params = cls.update_sql(data, where_condition)
        cls.connection.run(sql, params)

    @classmethod
    def select_sql(cls, columns: List[str] = None, where_condition: Optional[str] = None,
                   where_params: Optional[tuple] = None, order_by: Optional[List[str]] = None,
                   limit: Optional[int] = None, offset: Optional[int] = None,
                   joins: Optional[List[Dict[str, str]]] = None) -> Tuple[str, tuple]:
        """Generates SELECT SQL and parameters for the model."""
        if cls.dialect is None:
            raise ValueError("No SQL dialect defined for the model. Ensure connection is set.")
        table_name = cls.get_table_name()
        columns_to_select = columns if columns else ["*"]
        sql, _ = cls.dialect.select(table_name, columns_to_select, where_condition, order_by, limit, offset, joins)
        return sql, where_params or ()

    @classmethod
    def select(cls, columns: List[str] = None, where_condition: Optional[str] = None,
               where_params: Optional[tuple] = None, order_by: Optional[List[str]] = None,
               limit: Optional[int] = None, offset: Optional[int] = None,
               joins: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
        """Selects records based on various conditions."""
        if not cls.connection:
            raise OrmConnectionError("No database connection set. Call set_connection() on the BaseModel subclass.")
        sql, params = cls.select_sql(columns, where_condition, where_params, order_by, limit, offset, joins)
        return cls.connection.run(sql, params if params else None)

    def to_dict(self) -> dict:
        """
        Serializa os campos da instância que são BaseField em um dicionário.
        """
        fields, _ = self.__class__.get_fields()
        result = {}
        for name in fields:
            value = getattr(self, name)
            result[name] = value
        return result

    # -------------------------------------------------------------------------
    # Métodos async — executam os sync correspondentes em thread pool
    # -------------------------------------------------------------------------

    @classmethod
    async def async_select(cls, columns: List[str] = None, where_condition: Optional[str] = None,
                           where_params: Optional[tuple] = None, order_by: Optional[List[str]] = None,
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Versão assíncrona de select(), executa em thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: cls.select(columns, where_condition, where_params, order_by, limit)
        )

    @classmethod
    async def async_filter(cls, **conditions) -> List[Dict[str, Any]]:
        """Versão assíncrona de filter()."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: cls.filter(**conditions))

    @classmethod
    async def async_filter_delete(cls, **conditions) -> None:
        """Versão assíncrona de filter_delete()."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: cls.filter_delete(**conditions))

    @classmethod
    async def async_count(cls, **conditions) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: cls.count(**conditions))

    @classmethod
    async def async_exists(cls, **conditions) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: cls.exists(**conditions))

    @classmethod
    async def async_first(cls, **conditions) -> Optional[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: cls.first(**conditions))

    @classmethod
    async def async_last(cls, **conditions) -> Optional[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: cls.last(**conditions))

    @classmethod
    async def async_bulk_insert(cls, records: List[Dict[str, Any]]) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: cls.bulk_insert(records))

    @classmethod
    def upsert(
        cls,
        data: Dict[str, Any],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
    ) -> Any:
        """
        INSERT … ON CONFLICT … DO UPDATE (upsert).

        Insere o registro; se houver conflito nas ``conflict_columns`` (PK ou
        unique), atualiza as ``update_columns`` em vez de lançar erro.

        Args:
            data:              Dicionário ``{coluna: valor}`` para inserir.
            conflict_columns:  Colunas que definem o conflito (PK / unique index).
            update_columns:    Colunas a sobrescrever no conflito.
                               Padrão: todas as colunas que não estão em
                               ``conflict_columns``.

        Example::

            User.upsert(
                {"email": "a@b.com", "name": "Alice", "login_count": 1},
                conflict_columns=["email"],
                update_columns=["name", "login_count"],
            )
        """
        if not cls.connection:
            raise OrmConnectionError("Conexão não definida. Chame set_connection().")
        cls._cache.clear_prefix(cls.get_table_name())
        sql, params = cls.dialect.upsert(
            cls.get_table_name(), data, conflict_columns, update_columns
        )
        logger.debug("upsert() on %s conflict=%s", cls.get_table_name(), conflict_columns)
        return cls.connection.run(sql, params)

    @classmethod
    async def async_upsert(
        cls,
        data: Dict[str, Any],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None,
    ) -> Any:
        """Versão assíncrona de upsert()."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: cls.upsert(data, conflict_columns, update_columns)
        )

    async def async_refresh(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.refresh)

    @classmethod
    async def async_filter_update(cls, data: Dict[str, Any], **conditions) -> None:
        """Versão assíncrona de filter_update()."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: cls.filter_update(data, **conditions))

    # -------------------------------------------------------------------------
    # Carregamento de relacionamentos (select_related)
    # -------------------------------------------------------------------------

    @classmethod
    def select_related(cls, *field_names: str, **conditions) -> List[Dict[str, Any]]:
        """
        Retorna registros com objetos relacionados (FK) pré-carregados.

        Realiza apenas 1 query por FK field (batch via IN), evitando o problema
        N+1 de queries.

        Requer que os ``ForeignKeyField`` relevantes tenham ``to_model`` definido::

            class Post(BaseModel):
                author_id = ForeignKeyField("user", "id", to_model=User)

        Uso::

            posts = Post.select_related("author_id", status__eq="published")
            for post in posts:
                user = post["author_id_related"]   # dict do User relacionado

        Args:
            *field_names: Nomes dos campos FK a carregar.
            **conditions: Filtros aplicados ao SELECT principal (mesma sintaxe de filter()).

        Returns:
            Lista de dicts; cada dict tem ``<field_name>_related`` para cada FK carregado.
        """
        if not cls.connection:
            raise OrmConnectionError("Conexão não definida. Chame set_connection().")

        rows = cls.filter(**conditions) if conditions else cls.select()
        if not rows:
            return rows

        fields, _ = cls.get_fields()
        rows = [dict(row) for row in rows]  # cópia para não mutar os dicts originais

        for fname in field_names:
            field = fields.get(fname)
            if not isinstance(field, ForeignKeyField) or field.to_model is None:
                for row in rows:
                    row[f"{fname}_related"] = None
                continue

            col = field.db_column_name if field.db_column_name else fname
            fk_values = list({row[col] for row in rows if row.get(col) is not None})

            if not fk_values:
                for row in rows:
                    row[f"{fname}_related"] = None
                continue

            # Batch: 1 query com IN para todos os valores FK
            where, params = field.to_model.build_where_clause(
                {f"{field.reference_column}__in": fk_values}
            )
            related_rows = field.to_model.select(
                where_condition=where, where_params=params
            )
            related_map = {r[field.reference_column]: r for r in (related_rows or [])}

            for row in rows:
                fk_val = row.get(col)
                row[f"{fname}_related"] = related_map.get(fk_val)

        return rows

    @classmethod
    async def async_select_related(cls, *field_names: str,
                                   **conditions) -> List[Dict[str, Any]]:
        """Versão assíncrona de select_related()."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: cls.select_related(*field_names, **conditions)
        )

    @classmethod
    async def async_get(cls, **conditions):
        """Versão assíncrona de get()."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: cls.get(**conditions))

    async def async_save(self):
        """Versão assíncrona de save()."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.save)

    @classmethod
    async def async_update(cls, data: Dict[str, Any], where_condition: str):
        """Versão assíncrona de update()."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: cls.update(data, where_condition))

    @classmethod
    async def async_delete(cls, where_condition: str):
        """Versão assíncrona de delete()."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: cls.delete(where_condition))
