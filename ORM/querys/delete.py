from ..abstracts.querys import BaseQuery
from ..abstracts.connection_types import Connection
from ...exceptions import MissingWhereClauseError
from typing import Any, List, Tuple, Optional


class Delete(BaseQuery):
    """
    Query builder fluente para DELETE.

    Requer ao menos uma cláusula WHERE para evitar deleção acidental de
    todos os registros. Para forçar um DELETE sem WHERE, use ``force=True``::

        Delete("logs", client=conn).run(force=True)
    """

    def __init__(self, table_name: str = '', client: Connection = None):
        super().__init__(table_name)
        if client:
            self.set_connection(client)
        self._where_parts: List[str] = []

    def where(self, *conditions: str, operator: str = "AND") -> 'Delete':
        cond = f" {operator} ".join(conditions)
        if self._where_parts:
            self._where_parts.append(f"AND ({cond})")
        else:
            self._where_parts.append(f"({cond})")
        return self

    def or_where(self, *conditions: str) -> 'Delete':
        cond = " OR ".join(conditions)
        if self._where_parts:
            self._where_parts.append(f"OR ({cond})")
        else:
            self._where_parts.append(f"({cond})")
        return self

    def to_sql(self, force: bool = False) -> Tuple[str, Optional[tuple]]:
        if not self._where_parts and not force:
            raise MissingWhereClauseError(
                "DELETE sem cláusula WHERE removeria TODOS os registros. "
                "Adicione .where() ou use .run(force=True) para confirmar a intenção."
            )
        where_str = ' '.join(self._where_parts) if self._where_parts else '1=1'
        sql = self.dialect.delete(self._table_name, where_str)
        return sql, None

    def run(self, force: bool = False) -> Any:
        sql, params = self.to_sql(force=force)
        result = self.client.run(sql, params)
        return self.client.dialect.parser(result) if result else result
