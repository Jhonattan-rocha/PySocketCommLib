from ..abstracts.querys import BaseQuery
from ..abstracts.connection_types import Connection
from ..abstracts.dialetecs import SQLDialect
from typing import Dict, Any, List, Tuple

class Update(BaseQuery):
    def __init__(self, client: Connection, dialect: SQLDialect, table_name: str):
        super().__init__(client, dialect, table_name)
        self._update_clause: Dict[str, Any] = {}
        self._where_clause: List[str] = []

    def set(self, **kwargs):
        self._update_clause.update(kwargs)
        return self

    def where(self, *conditions, operator="AND"):
        condition_str = f" {operator} ".join(conditions)
        self._where_clause.append(condition_str)
        return self

    def to_sql(self) -> Tuple[str, tuple]:
        where_str = ' AND '.join(self._where_clause) if self._where_clause else '1=1' # 1=1 to update all if no where clause, careful usage needed
        return self.dialect.update(self._table_name, self._update_clause, where_str)

    def run(self) -> Any: # Run method for Update Query
        sql, params = self.to_sql()
        return self.client.run(sql, params)