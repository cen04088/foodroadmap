from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Table
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
    menu_items = relationship(
        "MenuItem", back_populates="restaurant", cascade="all, delete-orphan", order_by="MenuItem.position"
    )


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(String, ForeignKey("restaurants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    price_won = Column(Integer, nullable=True)
    # matzipmap 페이지에서 가게가 직접 <b class="pd-menu__tag">대표</b>로 표시한 메뉴인지 —
    # 목록 순서로 "대표 메뉴"를 추측하는 게 아니라 실제 사이트에 있는 큐레이션 신호를 그대로 쓴다.
    is_representative = Column(Boolean, nullable=False, default=False)
    position = Column(Integer, nullable=False, default=0)

    restaurant = relationship("Restaurant", back_populates="menu_items")


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

    restaurants = relationship(
        "Restaurant", secondary=restaurant_broadcasts, back_populates="broadcasts"
    )
