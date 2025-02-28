from ORM.dialetecs.psql import PsqlConnection
from ORM.models.model import BaseModel
from ORM.abstracts.field_types import IntegerField, TextField, JSONField, DateTimeField
from ORM.querys import Insert, Update, Delete, Select

conn = PsqlConnection(host="localhost", port=5432, user="postgres", password="123456", database="postgres") # Replace with your credentials
if conn.connect():
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
    print("Users inserted.")

    conn.disconnect()
else:
    print("Failed to connect to database.")