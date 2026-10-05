from dotenv import dotenv_values
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
import pytest


def test_product_database_role_cannot_connect_to_company(database_url):
    target = make_url(database_url).set(database="vf_company")
    engine = create_engine(target)
    try:
        with pytest.raises(OperationalError, match="permission denied for database"):
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def test_company_database_role_cannot_connect_to_product(database_url):
    config = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    target = make_url(database_url).set(username="vf_company", password=config["COMPANY_DB_PASSWORD"], database="vf_product")
    engine = create_engine(target)
    try:
        with pytest.raises(OperationalError, match="permission denied for database"):
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()
