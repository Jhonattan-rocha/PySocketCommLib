from .types import BaseField

class BaseModel:
    @classmethod
    def get_table_name(cls):
        # Por padrão, usa o nome da classe em snake_case como nome da tabela
        name = cls.__name__
        return ''.join(['_'+c.lower() if c.isupper() else c for c in name]).lstrip('_')

    @classmethod
    def create_table_sql(cls):
        table_name = cls.get_table_name()
        columns_definitions = []
        primary_key_columns = []

        for name, field in cls.__dict__.items():
            if isinstance(field, BaseField):
                db_column_name = field.db_column_name if field.db_column_name else name
                sql_type = field.get_sql_type()
                column_definition = f"{db_column_name} {sql_type}"
                if not field.nullable:
                    column_definition += " NOT NULL"
                if field.unique:
                    column_definition += " UNIQUE"
                if field.primary_key:
                    primary_key_columns.append(db_column_name)
                columns_definitions.append(column_definition)

        primary_key_constraint = ""
        if primary_key_columns:
            primary_key_constraint = f", PRIMARY KEY ({', '.join(primary_key_columns)})"

        return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_definitions)}{primary_key_constraint});"

    @classmethod
    def create_table(cls, client):
        sql = cls.create_table_sql()
        client.run(sql)
