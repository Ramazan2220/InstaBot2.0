"""
Тест для проверки работы SQLAlchemy
"""
try:
    import sqlalchemy
    print(f"SQLAlchemy успешно импортирован. Версия: {sqlalchemy.__version__}")

    # Проверяем базовую функциональность
    from sqlalchemy import create_engine, Column, Integer, String
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker

    # Создаем тестовую модель
    Base = declarative_base()

    class TestModel(Base):
        __tablename__ = 'test_table'
        id = Column(Integer, primary_key=True)
        name = Column(String)

    # Создаем тестовую базу данных в памяти
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)

    # Создаем сессию
    Session = sessionmaker(bind=engine)
    session = Session()

    # Добавляем тестовую запись
    test_record = TestModel(name="Test")
    session.add(test_record)
    session.commit()

    # Проверяем, что запись добавлена
    result = session.query(TestModel).first()
    print(f"Тестовая запись: id={result.id}, name={result.name}")

    print("SQLAlchemy работает корректно!")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
except Exception as e:
    print(f"Ошибка при тестировании SQLAlchemy: {e}")