
from typing import Optional
from datetime import date
from sqlalchemy import Integer, String, Date, Float
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    pass

class Transaction(Base):
    __tablename__ =  "bank_entries"

    transaction_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_date: Mapped[date] = mapped_column(Date)
    issuer: Mapped[str] = mapped_column(String(30))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    bank: Mapped[str] = mapped_column(String(10))
    category: Mapped[Optional[int]] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(String)

def main():
    engine = create_engine("sqlite:///auskunft.db", echo=True)
    Base.metadata.create_all(engine)


if __name__=="__main__":
    main()