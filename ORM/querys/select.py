from ..abstracts.querys import BaseQuery
from ..abstracts.connection_types import Connection
from typing import Any, List, Tuple


class Select(BaseQuery):
    """
    Query builder fluente para SELECT.

    Exemplo::

        result = (
            Select("orders", client=conn)
            .select("id", "total")
            .where("status = 'paid'")
            .or_where("status = 'pending'")
            .order_by("created_at", ascending=False)
            .group_by("status")
            .having("COUNT(*) > 1")
            .distinct()
            .limit(10)
            .offset(20)
            .run()
        )
    """

    def __init__(self, table_name: str = '', client: Connection = None):
        super().__init__(table_name)
        if client:
            self.set_connection(client)
        self._select_clause: List[str] = []
        self._from_clause: str = table_name
        self._where_parts: List[str] = []   # built with AND/OR prefixes
        self._order_by_clause: List[str] = []
        self._group_by_clause: List[str] = []
        self._having_clause: List[str] = []
        self._joins_clause: List[dict] = []
        self._limit_clause = None
        self._offset_clause = None
        self._distinct: bool = False

    # ------------------------------------------------------------------
    # Fluent methods
    # ------------------------------------------------------------------

    def select(self, *columns: str) -> 'Select':
        self._select_clause.extend(columns)
        return self

    def from_(self, table: str) -> 'Select':
        self._from_clause = table
        return self

    def distinct(self) -> 'Select':
        self._distinct = True
        return self

    def where(self, *conditions: str, operator: str = "AND") -> 'Select':
        """Adiciona condição(ões) unidas por `operator` ao WHERE com AND."""
        cond = f" {operator} ".join(conditions)
        if self._where_parts:
            self._where_parts.append(f"AND ({cond})")
        else:
            self._where_parts.append(f"({cond})")
        return self

    def or_where(self, *conditions: str) -> 'Select':
        """Adiciona condição(ões) ao WHERE com OR em relação às anteriores."""
        cond = " OR ".join(conditions)
        if self._where_parts:
            self._where_parts.append(f"OR ({cond})")
        else:
            self._where_parts.append(f"({cond})")
        return self

    def order_by(self, *columns: str, ascending: bool = True) -> 'Select':
        direction = "ASC" if ascending else "DESC"
        for col in columns:
            self._order_by_clause.append(f"{col} {direction}")
        return self

    def group_by(self, *columns: str) -> 'Select':
        self._group_by_clause.extend(columns)
        return self

    def having(self, *conditions: str, operator: str = "AND") -> 'Select':
        cond = f" {operator} ".join(conditions)
        if self._having_clause:
            self._having_clause.append(f"AND ({cond})")
        else:
            self._having_clause.append(f"({cond})")
        return self

    def limit(self, count: int) -> 'Select':
        if isinstance(count, int) and count > 0:
            self._limit_clause = count
        return self

    def offset(self, count: int) -> 'Select':
        if isinstance(count, int) and count >= 0:
            self._offset_clause = count
        return self

    def join(self, table: str, condition: str, join_type: str = "INNER") -> 'Select':
        self._joins_clause.append({
            "table": table,
            "condition": condition,
            "type": join_type.upper(),
        })
        return self

    def left_join(self, table: str, condition: str) -> 'Select':
        return self.join(table, condition, join_type="LEFT")

    def right_join(self, table: str, condition: str) -> 'Select':
        return self.join(table, condition, join_type="RIGHT")

    def full_outer_join(self, table: str, condition: str) -> 'Select':
        return self.join(table, condition, join_type="FULL OUTER")

    # ------------------------------------------------------------------
    # SQL generation
    # ------------------------------------------------------------------

    def to_sql(self) -> Tuple[str, tuple]:
        if not self._from_clause:
            raise ValueError("Cláusula FROM é obrigatória no SELECT.")

        where_str = ' '.join(self._where_parts) if self._where_parts else None

        sql, params = self.dialect.select(
            table_name=self._from_clause,
            columns=self._select_clause,
            where_condition=where_str,
            order_by=self._order_by_clause,
            limit=self._limit_clause,
            joins=self._joins_clause,
            offset=self._offset_clause,
        )

        # DISTINCT
        if self._distinct:
            sql = sql.replace('SELECT ', 'SELECT DISTINCT ', 1)

        # GROUP BY
        if self._group_by_clause:
            quoted = ', '.join(
                self.dialect.quote_identifier(c) for c in self._group_by_clause
            )
            sql += f" GROUP BY {quoted}"

        # HAVING
        if self._having_clause:
            sql += f" HAVING {' '.join(self._having_clause)}"

        return sql, params

    def run(self) -> Any:
        sql, params = self.to_sql()
        result = self.client.run(sql, params)
        return self.client.dialect.parser(result) if result else result
