class Query:
    def __init__(self, client):
        self.client = client
        self._select_clause = []
        self._from_clause = None
        self._where_clause = [] 
        self._order_by_clause = []
        self._limit_clause = None
        self._join_clause = [] 

    def select(self, *columns):
        self._select_clause.extend(columns)
        return self

    def from_(self, table):
        self._from_clause = table
        return self

    def where(self, condition):
        if isinstance(condition, list):
            self._where_clause.extend(condition)
        else:
            self._where_clause.append(condition)
        return self

    def and_where(self, condition):
        self._where_clause.append(condition)
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
        self._join_clause.append({"table": table, "condition": condition, "type": join_type.upper()})
        return self

    def left_join(self, table, condition):
        return self.join(table, condition, join_type="LEFT")

    def right_join(self, table, condition):
        return self.join(table, condition, join_type="RIGHT")

    def full_outer_join(self, table, condition):
        return self.join(table, condition, join_type="FULL OUTER")

    def to_sql(self):
        sql = "SELECT "
        if not self._select_clause:
            sql += "*"
        else:
            sql += ", ".join(self._select_clause)

        if self._from_clause:
            sql += f" FROM {self._from_clause}"

            if self._join_clause:
                for join_info in self._join_clause:
                    sql += f" {join_info['type']} JOIN {join_info['table']} ON {join_info['condition']}"

        if self._where_clause:
            # Junta multiplas condições WHERE com AND. Ajustar para OR complexos seria mais elaborado.
            sql += " WHERE " + " AND ".join(self._where_clause) if self._where_clause else ""


        if self._order_by_clause:
            sql += " ORDER BY " + ", ".join(self._order_by_clause)

        if self._limit_clause is not None:
            sql += f" LIMIT {self._limit_clause}"

        return sql

    def fetch(self):
        sql_query = self.to_sql()
        return self.client.run(sql_query)