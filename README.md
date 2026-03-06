Order Management API

A backend API built with FastAPI and PostgreSQL for managing users, products and orders in a simple e-commerce system.
This project demonstrates core backend concepts such as order creation, stock validation, order preview simulation and basic sales analytics.

---

Technologies

Python  
FastAPI  
PostgreSQL  
SQLAlchemy  
Uvicorn  

---

Features

Create and list users  
Create and list products  
Create orders with stock validation  
Preview orders before creation  
List all orders  
List orders of a specific user  
Update order status  
Restore stock when a pending order is cancelled  
Analytics endpoint for top-selling products  

API Endpoints

| Method | Endpoint | Description |
|------|------|------|
| POST | /users | Create a new user |
| GET | /users | List all users |
| POST | /products | Create a new product |
| GET | /products | List all products |
| POST | /orders | Create an order |
| POST | /orders/preview | Preview order without creating it |
| GET | /orders | List all orders |
| GET | /orders/{order_id} | Get order details |
| GET | /users/{user_id}/orders | Get orders of a user |
| PATCH | /orders/{order_id}/status | Update order status |
| GET | /analytics/top-products | Get top selling products |

---

Order Status Flow

pending → paid → shipped → delivered  
pending → cancelled

If an order is cancelled while still in pending state, the product stock is restored.

---

How to Run

Clone the repository
git clone https://github.com/YOUR_USERNAME/order-management-api.git

Go to the project folder
cd order-management-api

Create virtual environment
python3 -m venv venv  
source venv/bin/activate  

Install dependencies
pip install -r requirements.txt  

Create a .env file and add
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/ecommerce

Run the server
python -m uvicorn main:app --reload

Open Swagger
http://127.0.0.1:8000/docs

---

Author  
Hivda Akan
