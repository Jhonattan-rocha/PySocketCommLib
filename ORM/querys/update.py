from ..abstracts.querys import BaseQuery
from ..abstracts.connection_types import Connection
from typing import Dict, Any, List, Tuple


class Update(BaseQuery):
    """
    Query builder fluente para UPDATE.

    Requer ao menos uma cláusula WHERE para evitar atualização acidental de
    todos os registros. Para forçar um UPDATE sem WHERE, use ``force=True``::

        Update("users", client=conn).set(active=False).run(force=True)
    """

    def __init__(self, table_name: str = '', client: Connection = None):
        super().__init__(table_name)
        if client:
            self.set_connection(client)
        self._update_clause: Dict[str, Any] = {}
        self._where_parts: List[str] = []

    def set(self, **kwargs) -> 'Update':
        self._update_clause.update(kwargs)
        return self

    def where(self, *conditions: str, operator: str = "AND") -> 'Update':
        cond = f" {operator} ".join(conditions)
        if self._where_parts:
            self._where_parts.append(f"AND ({cond})")
        else:
            self._where_parts.append(f"({cond})")
        return self

    def or_where(self, *conditions: str) -> 'Update':
        cond = " OR ".join(conditions)
        if self._where_parts:
            self._where_parts.append(f"OR ({cond})")
        else:
            self._where_parts.append(f"({cond})")
        return self

    def to_sql(self, force: bool = False) -> Tuple[str, tuple]:
        if not self._where_parts and not force:
            raise ValueError(
                "UPDATE sem cláusula WHERE atualizaria TODOS os registros. "
                "Adicione .where() ou use .run(force=True) para confirmar a intenção."
            )
        where_str = ' '.join(self._where_parts) if self._where_parts else '1=1'
        return self.dialect.update(self._table_name, self._update_clause, where_str)

    def run(self, force: bool = False) -> Any:
        sql, params = self.to_sql(force=force)
        result = self.client.run(sql, params)
        return self.client.dialect.parser(result) if result else result
