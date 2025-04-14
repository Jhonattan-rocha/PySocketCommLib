from ORM.dialetecs.psql import PsqlConnection
from ORM.models.model import BaseModel
from ORM.abstracts.querys import BaseQuery
from ORM.abstracts.field_types import IntegerField, TextField, DateTimeField
from ORM.querys import Insert, Update

conn = PsqlConnection(host="localhost", port=5432, user="postgres", password="19751983", database="postgres")
if conn.connect():
    BaseQuery.set_connection(conn)
    BaseModel.set_connection(conn) # Set connection for BaseModel

    # Define a Model
    class User(BaseModel):
        id = IntegerField(primary_key=True)
        name = TextField(nullable=False)
        age = IntegerField(nullable=True)
        signup_date = DateTimeField(default="NOW()") # Example default value
        data = TextField(nullable=True) # Example JSON field

    # Create Table
    User.create_table()
    print(f"Table '{User.get_table_name()}' created.")

    # Insert Data
    user1 = User(id=1, name="Alice", age=30, data='{"city": "New York"}')
    user1.save()
    user2 = User(id=2, name="Bob", age=25, data='{"city": "Los Angeles"}')
    user2.save()
    user3 = Insert(User.get_table_name()).values(id=3, name="Junior", age=30, data='{"city": "São Paulo"}')
    user3.run()

    Update(User.get_table_name()).set(name="Alice2").where("id = 1").run()

    print("Users inserted.")

    conn.disconnect()
else:
    print("Failed to connect to database.")