from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, User, Product, Order, OrderItem
from sqlalchemy import func


app = FastAPI()

Base.metadata.create_all(bind=engine)

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class ProductCreate(BaseModel):
    name: str
    price: float
    stock: int

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    user_id: int
    items: list[OrderItemCreate]

class OrderStatusUpdate(BaseModel):
    status: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.post("/users")
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(name=payload.name, email=payload.email, password=payload.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email}

@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "name": u.name, "email": u.email} for u in users]

@app.post("/products")
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    if payload.price <= 0:
        raise HTTPException(status_code=400, detail="Price must be positive")
    if payload.stock < 0:
        raise HTTPException(status_code=400, detail="Stock cannot be negative")

    product = Product(name=payload.name, price=payload.price, stock=payload.stock)
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": product.id, "name": product.name, "price": float(product.price), "stock": product.stock}


@app.get("/products")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": float(p.price),
            "stock": p.stock
        }
        for p in products
    ]

@app.post("/orders")

def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    try:
        # user var mı?
        user = db.query(User).filter(User.id == payload.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not payload.items:
            raise HTTPException(status_code=400, detail="Order must contain at least 1 item")

        total = 0.0
        resolved_items = []

        # ürünleri kontrol et + total hesapla
        for item in payload.items:
            if item.quantity <= 0:
                raise HTTPException(status_code=400, detail="Quantity must be > 0")

            product = (
                db.query(Product)
                .filter(Product.id == item.product_id)
                .with_for_update()  # sql'de SELECT ... FOR UPDATE -> bu satırdaki veriyi kilitle, diğer transaction'lar beklesin
                .first()
            )
            if not product:
                raise HTTPException(status_code=404, detail=f"Product not found: {item.product_id}")

            if product.stock < item.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for product {product.id}")

            unit_price = float(product.price)
            total += unit_price * item.quantity
            resolved_items.append((product, item.quantity, unit_price))

        # order oluştur
        order = Order(user_id=payload.user_id, status="pending", total_amount=total)
        db.add(order)
        db.flush()  # order.id gelsin diye (commit değil)

        # order_items yaz + stok düş
        for product, qty, unit_price in resolved_items:
            db.add(OrderItem(order_id=order.id, product_id=product.id, quantity=qty, unit_price=unit_price))
            product.stock -= qty

        db.commit()
        db.refresh(order)

        return {
            "order_id": order.id,
            "user_id": order.user_id,
            "status": order.status,
            "total_amount": float(order.total_amount)
        }
    except Exception:
        db.rollback()
        raise

@app.post("/orders/preview")
def preview_order(payload: OrderCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least 1 item")

    total = 0.0
    preview_items = []

    for item in payload.items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be > 0")

        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {item.product_id}")

        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {product.id}")

        unit_price = float(product.price)
        item_total = unit_price * item.quantity
        total += item_total

        preview_items.append({
            "product_id": product.id,
            "product_name": product.name,
            "quantity": item.quantity,
            "unit_price": unit_price,
            "item_total": item_total
        })

    return {
        "valid": True,
        "user_id": payload.user_id,
        "total_amount": total,
        "items": preview_items
    }

@app.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()

    return {
        "order_id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price)
            }
            for item in items
        ]
    }

@app.patch("/orders/{order_id}/status")
def update_order_status(order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    valid_transitions = {
        "pending": ["paid", "cancelled"],
        "paid": ["shipped"],
        "shipped": ["delivered"],
        "delivered": [],
        "cancelled": []
    }

    if payload.status not in valid_transitions[order.status]:
        raise HTTPException(status_code=400, detail="Invalid status transition")

    if payload.status == "cancelled":
        items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()

        for item in items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            product.stock += item.quantity

    order.status = payload.status

    db.commit()
    db.refresh(order)

    return {
        "order_id": order.id,
        "new_status": order.status
    }

@app.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).all()

    return [
        {
            "order_id": order.id,
            "user_id": order.user_id,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "created_at": order.created_at,
        }
        for order in orders
    ]

@app.get("/users/{user_id}/orders")
def get_user_orders(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    orders = db.query(Order).filter(Order.user_id == user_id).all()

    return [
        {
            "order_id": order.id,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "created_at": order.created_at,
        }
        for order in orders
    ]

@app.get("/analytics/top-products")
def top_products(db: Session = Depends(get_db)):
    results = (
        db.query(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            func.sum(OrderItem.quantity).label("total_sold"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("total_revenue")
        )
        .join(OrderItem, Product.id == OrderItem.product_id)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .all()
    )

    return [
        {
            "product_id": row.product_id,
            "product_name": row.product_name,
            "total_sold": int(row.total_sold),
            "total_revenue": float(row.total_revenue)
        }
        for row in results
    ]