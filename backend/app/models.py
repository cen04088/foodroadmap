from sqlalchemy import Column, String, Float, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

restaurant_broadcasts = Table(
    "restaurant_broadcasts",
    Base.metadata,
    Column("restaurant_id", String, ForeignKey("restaurants.id"), primary_key=True),
    Column("broadcast_id", String, ForeignKey("broadcasts.id"), primary_key=True),
)


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    hours = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    youtube_url = Column(String, nullable=True)

    broadcasts = relationship(
        "Broadcast", secondary=restaurant_broadcasts, back_populates="restaurants"
    )


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    restaurants = relationship(
        "Restaurant", secondary=restaurant_broadcasts, back_populates="broadcasts"
    )
