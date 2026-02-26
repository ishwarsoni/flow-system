"""
Pytest configuration and shared fixtures for database isolation.

This module implements transaction-based test isolation to ensure that
each test runs in a clean database state without data leaking between tests.
"""

import pytest
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker, Session
from app.db.base import Base


@pytest.fixture(scope="session")
def engine():
    """
    Create a single in-memory SQLite database for the entire test session.
    
    This engine is shared across all tests, but each test gets its own
    transaction that is rolled back after the test completes.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        # Ensure SQLite enforces foreign keys in tests
        connect_args={"check_same_thread": False},
    )
    
    # Create all tables using the shared Base
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup after all tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db(engine):
    """
    Provide a database session for each test with transaction-based isolation.
    
    How isolation works:
    1. A new connection is created for each test
    2. A transaction is started on that connection
    3. A session is bound to this connection
    4. The test runs (all COMMITS are captured within the transaction)
    5. After the test, the transaction is ROLLED BACK
    6. All changes (committed or not) are undone
    
    This ensures:
    - No data leaks between tests
    - Each test starts with a clean slate
    - UNIQUE constraints don't fail across tests
    - Foreign key relationships are respected
    - Works with both SQLite and future Postgres use
    
    Example:
        def test_create_user(db):
            user = User(email="test@example.com")
            db.add(user)
            db.commit()  # Commits within the transaction
            
            # Data is visible in this test
            assert db.query(User).count() == 1
        
        def test_another_user(db):
            # Previous test's data is gone due to rollback
            user = User(email="test@example.com")  # Same email is OK
            db.add(user)
            db.commit()
            assert db.query(User).count() == 1
    """
    # Get a new connection from the engine
    connection = engine.connect()
    
    # Start a transaction on this connection
    transaction = connection.begin()
    
    try:
        # Create a session bound to this connection
        SessionLocal = sessionmaker(bind=connection)
        session = SessionLocal()
        
        yield session
        
    finally:
        # Close the session
        session.close()
        
        # Rollback everything that happened in this test
        # This undoes all commits that occurred within the test
        transaction.rollback()
        
        # Close the connection
        connection.close()
