import unittest
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    create_engine,
    MetaData,
    Table,
    text,
    func,
    select,
    insert,
    update,
    delete,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    scoped_session,
)

# --- SQLAlchemy ORM setup -----------------------------------------------------

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    fullname = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"User(id={self.id!r}, username={self.username!r})"


class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email = Column(String(120), nullable=False)

    user = relationship("User", back_populates="addresses")

    def __repr__(self):
        return f"Address(id={self.id!r}, email={self.email!r})"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)

    order_items = relationship("OrderItem", back_populates="product")

    def __repr__(self):
        return f"Product(id={self.id!r}, name={self.name!r})"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Order(id={self.id!r}, user_id={self.user_id!r})"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

    def __repr__(self):
        return f"OrderItem(id={self.id!r}, quantity={self.quantity!r})"


# --- Test suite --------------------------------------------------------------


class SQLAlchemyModuleTest(unittest.TestCase):
    """A reasonably broad test suite exercising common SQLAlchemy Core + ORM features."""

    @classmethod
    def setUpClass(cls):
        # Create in-memory SQLite engine and all tables
        cls.engine = create_engine("sqlite:///:memory:", echo=False, future=True)
        Base.metadata.create_all(cls.engine)

        # Use sessionmaker + scoped_session to cover those APIs too
        cls._session_factory = sessionmaker(bind=cls.engine, autoflush=False, future=True)
        cls.Session = scoped_session(cls._session_factory)

        # Seed some basic data
        session = cls.Session()
        try:
            user = User(username="alice", fullname="Alice Wonderland")
            user.addresses.append(Address(email="alice@example.com"))
            user.addresses.append(Address(email="a.wonderland@example.org"))

            bob = User(username="bob", fullname="Bob Builder", is_active=False)
            bob.addresses.append(Address(email="bob@example.com"))

            p1 = Product(name="Widget", price=9.99)
            p2 = Product(name="Gadget", price=19.99)
            p3 = Product(name="Thingy", price=1.99)

            order = Order(user=user)
            order.items.append(OrderItem(product=p1, quantity=2))
            order.items.append(OrderItem(product=p2, quantity=1))

            session.add_all([user, bob, p1, p2, p3, order])
            session.commit()
        finally:
            session.close()

    @classmethod
    def tearDownClass(cls):
        # Drop tables and dispose engine
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()
        cls.Session.remove()

    def setUp(self):
        self.session = self.Session()

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    # --- ORM basics ----------------------------------------------------------

    def test_orm_query_basic_filter_and_order(self):
        # Basic SELECT with filter, order_by, scalar() usage
        q = (
            self.session.query(User)
            .filter(User.username.in_(["alice", "bob"]))
            .order_by(User.username.asc())
        )
        users = q.all()
        self.assertEqual([u.username for u in users], ["alice", "bob"])

        active_users = (
            self.session.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.id)
            .all()
        )
        self.assertEqual(len(active_users), 1)
        self.assertEqual(active_users[0].username, "alice")

    def test_orm_relationship_lazy_loading_and_cascade(self):
        # Access relationships and ensure they are loaded
        alice = self.session.query(User).filter_by(username="alice").one()
        self.assertGreaterEqual(len(alice.addresses), 1)

        order = self.session.query(Order).filter(Order.user == alice).one()
        self.assertGreaterEqual(len(order.items), 1)
        self.assertEqual(order.items[0].order, order)

        # Cascading delete: when we delete a user, their orders and addresses are deleted
        self.session.delete(alice)
        self.session.commit()

        remaining_users = [u.username for u in self.session.query(User).all()]
        self.assertNotIn("alice", remaining_users)

        # Recreate alice to not impact other tests too heavily
        alice = User(username="alice2", fullname="Alice Recreated")
        self.session.add(alice)
        self.session.commit()

    def test_orm_update_and_delete(self):
        bob = self.session.query(User).filter_by(username="bob").one()
        self.assertFalse(bob.is_active)

        # Update using ORM
        bob.is_active = True
        self.session.commit()

        refreshed_bob = self.session.query(User).filter_by(username="bob").one()
        self.assertTrue(refreshed_bob.is_active)

        # Delete using ORM
        self.session.delete(refreshed_bob)
        self.session.commit()

        remaining_usernames = [u.username for u in self.session.query(User).all()]
        self.assertNotIn("bob", remaining_usernames)

    # --- SQL Expression language (Core) --------------------------------------

    def test_core_insert_select_update_delete(self):
        metadata = MetaData()
        # Define a new table with Core to exercise Table / Column / MetaData
        temp_table = Table(
            "temp_numbers",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("value", Integer, nullable=False),
        )
        metadata.create_all(self.engine)

        with self.engine.begin() as conn:
            # INSERT
            conn.execute(
                insert(temp_table),
                [{"value": 10}, {"value": 20}, {"value": 30}],
            )

            # SELECT
            result = conn.execute(
                select(temp_table.c.value).order_by(temp_table.c.value.asc())
            )
            values = [row[0] for row in result]
            self.assertEqual(values, [10, 20, 30])

            # UPDATE
            conn.execute(
                update(temp_table)
                .where(temp_table.c.value == 20)
                .values(value=25)
            )
            result = conn.execute(
                select(temp_table.c.value)
                .where(temp_table.c.value >= 20)
                .order_by(temp_table.c.value.asc())
            )
            values = [row[0] for row in result]
            self.assertEqual(values, [25, 30])

            # DELETE
            conn.execute(delete(temp_table).where(temp_table.c.value == 25))
            result = conn.execute(select(func.count()).select_from(temp_table))
            count_after_delete = result.scalar_one()
            self.assertEqual(count_after_delete, 2)

        metadata.drop_all(self.engine)

    def test_core_text_and_bindparams(self):
        with self.engine.begin() as conn:
            # Simple text() query with bound parameters
            result = conn.execute(
                text("SELECT username FROM users WHERE username LIKE :pattern"),
                {"pattern": "alice%"},
            )
            names = [row[0] for row in result]
            # Depending on previous tests, user might be "alice" or "alice2" or both
            self.assertTrue(any(name.startswith("alice") for name in names))

    def test_core_aggregates_and_joins(self):
        # Join orders -> items -> products and aggregate totals
        stmt = (
            select(
                User.username,
                func.sum(Product.price * OrderItem.quantity).label("total_spent"),
            )
            .join(Order, Order.user_id == User.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(Product, Product.id == OrderItem.product_id)
            .group_by(User.username)
        )

        rows = self.session.execute(stmt).all()
        for username, total in rows:
            if username.startswith("alice"):
                self.assertGreater(total, 0)

    # --- Modern 2.x style select() with ORM entities -------------------------

    def test_select_orm_entities_with_future_style(self):
        stmt = select(User).where(User.username.like("alice%")).order_by(User.username)
        result = self.session.execute(stmt)
        users = result.scalars().all()
        self.assertTrue(len(users) >= 1)
        for user in users:
            self.assertIsInstance(user, User)

    # --- Transactions / rollback ---------------------------------------------

    def test_transaction_and_rollback(self):
        # Insert a product, then roll back
        new_product = Product(name="RollbackProduct", price=123.45)
        self.session.add(new_product)
        self.session.flush()
        self.assertIsNotNone(new_product.id)

        # Rollback
        self.session.rollback()

        # Product should not be present anymore
        p = self.session.query(Product).filter_by(name="RollbackProduct").all()
        self.assertEqual(p, [])

    # --- Reflection / MetaData introspection ---------------------------------

    def test_metadata_reflection(self):
        # Reflect existing schema
        reflected_meta = MetaData()
        reflected_meta.reflect(bind=self.engine)

        # Check that known tables are present
        for table_name in ["users", "addresses", "products", "orders", "order_items"]:
            self.assertIn(table_name, reflected_meta.tables)

        users_table = reflected_meta.tables["users"]
        self.assertIn("username", users_table.c)

    # --- Scoped session behavior ---------------------------------------------

    def test_scoped_session_identity_map(self):
        """
        scoped_session should return the same Session instance within the same thread,
        so the identity map is shared across calls.
        """
        # Object loaded via self.session
        user1 = self.session.query(User).filter(User.username.like("alice%")).first()
        user2 = self.session.query(User).filter(User.id == user1.id).one()
        self.assertIs(user1, user2)  # same identity in same Session

        # Calling the scoped_session again in the same thread yields the same Session
        other_session = self.Session()
        try:
            # same underlying Session object
            self.assertIs(self.session, other_session)

            user3 = other_session.query(User).filter(User.id == user1.id).one()
            # same identity map, so same Python object
            self.assertIs(user1, user3)
        finally:
            other_session.close()

    # --- Eager loading / joinedload-like via explicit join -------------------

    def test_joinedload_like_behavior_via_join(self):
        # Simulate eager loading pattern via explicit join
        stmt = (
            select(User, Address)
            .join(Address, User.id == Address.user_id)
            .where(User.username.like("alice%"))
        )
        rows = self.session.execute(stmt).all()
        self.assertGreaterEqual(len(rows), 1)
        # rows are tuples (User, Address)
        for user, addr in rows:
            self.assertEqual(user.id, addr.user_id)


if __name__ == "__main__":
    unittest.main()
