from ..abstracts.field_types import BaseField
from ..abstracts.dialetecs import SQLDialect  # Importando o dialeto

class BaseModel:
    dialect: SQLDialect = None  # Define um dialeto como padrão

    @classmethod
    def get_table_name(cls):
        # Converte o nome da classe para snake_case
        name = cls.__name__
        return ''.join(['_'+c.lower() if c.isupper() else c for c in name]).lstrip('_')

    @classmethod
    def create_table_sql(cls):
        if cls.dialect is None:
            raise ValueError("Nenhum dialeto SQL definido para o modelo.")

        table_name = cls.get_table_name()
        columns_definitions = []
        primary_key_columns = []

        for name, field in cls.__dict__.items():
            if isinstance(field, BaseField):
                db_column_name = field.db_column_name if field.db_column_name else name
                sql_type = cls.dialect.get_sql_type(field)
                column_definition = f"{db_column_name} {sql_type}"

                if not field.nullable:
                    column_definition += " NOT NULL"
                if field.unique:
                    column_definition += " UNIQUE"
                if field.primary_key:
                    primary_key_columns.append(db_column_name)

                columns_definitions.append(column_definition)

        primary_key_constraint = cls.dialect.get_primary_key_constraint(primary_key_columns)

        return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_definitions)}{primary_key_constraint});"

    @classmethod
    def create_table(cls, client):
        sql = cls.create_table_sql()
        client.run(sql)
