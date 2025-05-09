from ..abstracts.querys import BaseQuery
from ..abstracts.connection_types import Connection
from typing import Any, Tuple

class Select(BaseQuery):
    def __init__(self, table_name: str='', client: Connection=None):
        super().__init__(table_name)
        if client:
            self.set_connection(client)
        self._select_clause = []
        self._from_clause = table_name
        self._where_clause = []
        self._order_by_clause = []
        self._limit_clause = None
        self._joins_clause = []

    def select(self, *columns):
        self._select_clause.extend(columns)
        return self

    def from_(self, table):
        self._from_clause = table
        return self

    def where(self, *conditions, operator="AND"):
        condition_str = f" {operator} ".join(conditions)
        self._where_clause.append(condition_str)
        return self

    def or_where(self, condition):
        self._where_clause.append(f"OR {condition}")
        return self

    def order_by(self, *columns, ascending=True):
        order_direction = "ASC" if ascending else "DESC"
        for col in columns:
            self._order_by_clause.append(f"{col} {order_direction}")
        return self

    def limit(self, count):
        if isinstance(count, int) and count > 0:
            self._limit_clause = count
        return self

    def join(self, table, condition, join_type="INNER"):
        self._joins_clause.append({"table": table, "condition": condition, "type": join_type.upper()}) # Use _joins_clause
        return self

    def left_join(self, table, condition):
        return self.join(table, condition, join_type="LEFT")

    def right_join(self, table, condition):
        return self.join(table, condition, join_type="RIGHT")

    def full_outer_join(self, table, condition):
        return self.join(table, condition, join_type="FULL OUTER")

    def to_sql(self) -> Tuple[str, tuple]:
        if not self._from_clause:
            raise ValueError("FROM clause is required for SELECT query.")

        return self.dialect.select(
            table_name=self._from_clause, # Use _from_clause for table name
            columns=self._select_clause,
            where_condition=self._where_clause, # Pass where as is, dialect handles joining
            order_by=self._order_by_clause,
            limit=self._limit_clause,
            joins=self._joins_clause # Use _joins_clause
        )

    def run(self) -> Any: # Run method for Select Query
        sql, params = self.to_sql()
        return self.client.dialect.parser(self.client.run(sql, params))
