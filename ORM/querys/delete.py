from ..abstracts.querys import BaseQuery
from ..abstracts.connection_types import Connection
from typing import Any, List, Tuple, Optional

class Delete(BaseQuery):
    def __init__(self, table_name: str='', client: Connection=None):
        super().__init__(table_name)
        if client:
            self.set_connection(client)
        self._where_clause: List[str] = []

    def where(self, *conditions, operator="AND"):
        condition_str = f" {operator} ".join(conditions)
        self._where_clause.append(condition_str)
        return self

    def to_sql(self) -> Tuple[str, Optional[tuple]]: # Modified to return SQL and params
        sql = self.dialect.delete(self._table_name, ' AND '.join(self._where_clause) if self._where_clause else '1=1') # 1=1 if no where clause for delete all
        return sql, None # Delete queries usually don't have parameters in basic WHERE clauses

    def run(self) -> Any: # Run method for Delete Query
        sql, params = self.to_sql()
        result = self.client.run(sql, params)
        return self.client.dialect.parser(result) if result else result
