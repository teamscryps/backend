from sqlalchemy import create_engine

DATABASE_URL = "postgresql://postgres:1234@localhost:5432/scryps_db"
engine=create_engine(DATABASE_URL, echo=True)

try:
    with engine.connect() as conn:
        print("Connection to the database was successful.")
except Exception as e:
    print(f"An error occurred while connecting to the database: {e}")