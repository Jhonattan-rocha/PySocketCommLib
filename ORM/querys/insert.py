from ..abstracts.querys import BaseQuery
from ..abstracts.connection_types import Connection
from ..abstracts.dialetecs import SQLDialect
from typing import Any, Dict, Tuple

class Insert(BaseQuery): # Added Insert query builder
    def __init__(self, client: Connection, dialect: SQLDialect, table_name: str):
        super().__init__(client, dialect, table_name)
        self._data_to_insert: Dict[str, Any] = {}

    def values(self, **kwargs):
        self._data_to_insert.update(kwargs)
        return self

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.insert(self._table_name, self._data_to_insert)

    def run(self) -> Any: # Run method for Insert Query
        sql, params = self.to_sql()
        return self.client.run(sql, params)