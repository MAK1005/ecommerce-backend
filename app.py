from dotenv import load_dotenv
import os
load_dotenv()
import bcrypt
from datetime import datetime
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)

# create flask app
app = Flask(__name__)

# mysql connection
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1234@localhost/ecommerce'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY') or 'fallback-secret'
jwt = JWTManager(app)

# initialize db
db = SQLAlchemy(app)

# users table model
class Users(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(20), default='user')

# products table model
class Products(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    stock = db.Column(db.Integer)

# cart table model
class Cart(db.Model):
    __tablename__ = 'cart'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

# cart items table model
class CartItems(db.Model):
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer)

# orders table model
class Orders(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    total_price = db.Column(db.Float)
    status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime)

# order items table model
class OrderItems(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    quantity = db.Column(db.Integer)

@app.route('/')
def home():
    return "E-commerce backend is running!"

# get all products
@app.route('/products', methods=['GET'])
def get_products():
    products = Products.query.all()

    result = []
    for p in products:
        result.append({
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "stock": p.stock
        })

    return {"products": result}

# register new user
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return {"error": "Username, email and password are required"}, 400

    existing_user = Users.query.filter_by(email=data['email']).first()
    if existing_user:
        return {"error": "Email already registered"}, 409

    hashed_password = bcrypt.hashpw(
        data['password'].encode('utf-8'),
        bcrypt.gensalt()
    )

    new_user = Users(
        username=data['username'],
        email=data['email'],
        password=hashed_password.decode('utf-8'),
        role=data.get('role', 'user')
    )

    db.session.add(new_user)
    db.session.commit()

    return {"message": "User registered successfully"}

# login user
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return {"error": "Email and password are required"}, 400

    user = Users.query.filter_by(email=data['email']).first()

    if not user:
        return {"error": "User not found"}, 404

    if bcrypt.checkpw(
        data['password'].encode('utf-8'),
        user.password.encode('utf-8')
    ):
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={"role": user.role}
        )

        return {
            "message": "Login successful",
            "access_token": access_token,
            "user_id": user.id,
            "role": user.role
        }

    return {"error": "Invalid password"}, 401

# add a new product (admin only)
@app.route('/add-product', methods=['POST'])
@jwt_required()
def add_product():
    data = request.get_json()

    user_id = int(get_jwt_identity())
    db.session.get(Users, id)

    if not data:
        return {"error": "No data provided"}, 400

    if not user:
        return {"error": "User not found"}, 404

    if user.role != 'admin':
        return {"error": "Only admin can add products"}, 403

    if not data.get('name') or data.get('price') is None or data.get('stock') is None:
        return {"error": "Name, price and stock are required"}, 400

    new_product = Products(
        name=data['name'],
        description=data.get('description', ''),
        price=data['price'],
        stock=data['stock']
    )

    db.session.add(new_product)
    db.session.commit()

    return {"message": "Product added successfully"}

# add product to cart
@app.route('/add-to-cart', methods=['POST'])
@jwt_required()
def add_to_cart():
    data = request.get_json()

    if not data:
        return {"error": "No data provided"}, 400

    user_id = int(get_jwt_identity())
    product_id = data.get('product_id')
    quantity = data.get('quantity')

    if not product_id or not quantity:
        return {"error": "product_id and quantity are required"}, 400

    if quantity <= 0:
        return {"error": "Quantity must be greater than 0"}, 400

    user = Users.query.get(user_id)
    if not user:
        return {"error": "User not found"}, 404

    product = Products.query.get(product_id)
    if not product:
        return {"error": "Product not found"}, 404

    cart = Cart.query.filter_by(user_id=user_id).first()
    if not cart:
        cart = Cart(user_id=user_id)
        db.session.add(cart)
        db.session.commit()

    existing_item = CartItems.query.filter_by(cart_id=cart.id, product_id=product_id).first()

    if existing_item:
        new_total_quantity = existing_item.quantity + quantity
        if new_total_quantity > product.stock:
            return {"error": "Not enough stock available"}, 400
        existing_item.quantity = new_total_quantity
    else:
        if quantity > product.stock:
            return {"error": "Not enough stock available"}, 400

        cart_item = CartItems(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)

    db.session.commit()

    return {"message": "Product added to cart successfully"}

# view cart items for a user
@app.route('/cart', methods=['GET'])
@jwt_required()
def view_cart():
    user_id = int(get_jwt_identity())

    cart = Cart.query.filter_by(user_id=user_id).first()

    if not cart:
        return {"user_id": user_id, "cart_items": [], "cart_total": 0}

    cart_items = CartItems.query.filter_by(cart_id=cart.id).all()

    result = []
    total = 0

    for item in cart_items:
        product = Products.query.get(item.product_id)
        if product:
            item_total = product.price * item.quantity
            total += item_total

            result.append({
                "product_id": product.id,
                "name": product.name,
                "price": product.price,
                "quantity": item.quantity,
                "item_total": item_total
            })

    return {
        "user_id": user_id,
        "cart_items": result,
        "cart_total": total
    }

# checkout route -> create order from cart
@app.route('/checkout', methods=['POST'])
@jwt_required()
def checkout():
    user_id = int(get_jwt_identity())

    cart = Cart.query.filter_by(user_id=user_id).first()

    if not cart:
        return {"error": "Cart not found"}, 404

    cart_items = CartItems.query.filter_by(cart_id=cart.id).all()

    if not cart_items:
        return {"error": "Cart is empty"}, 400

    total = 0

    for item in cart_items:
        product = Products.query.get(item.product_id)

        if not product:
            return {"error": f"Product with id {item.product_id} not found"}, 404

        if item.quantity > product.stock:
            return {"error": f"Not enough stock for {product.name}"}, 400

        total += product.price * item.quantity

    new_order = Orders(
        user_id=user_id,
        total_price=total,
        status='placed',
        created_at=datetime.utcnow()
    )

    db.session.add(new_order)
    db.session.commit()

    for item in cart_items:
        product = Products.query.get(item.product_id)

        order_item = OrderItems(
            order_id=new_order.id,
            product_id=item.product_id,
            quantity=item.quantity
        )

        db.session.add(order_item)
        product.stock -= item.quantity

    for item in cart_items:
        db.session.delete(item)

    db.session.commit()

    return {
        "message": "Order placed successfully",
        "order_id": new_order.id,
        "total_price": total,
        "status": new_order.status
    }

# test protected route
@app.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    current_user_id = int(get_jwt_identity())
    user = Users.query.get(current_user_id)

    if not user:
        return {"error": "User not found"}, 404

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role
    }

@app.route('/search-products', methods=['GET'])
def search_products():
    name = request.args.get('name')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')

    query = Products.query

    # filter by name
    if name:
        query = query.filter(Products.name.ilike(f"%{name}%"))

    # filter by min price
    if min_price:
        query = query.filter(Products.price >= float(min_price))

    # filter by max price
    if max_price:
        query = query.filter(Products.price <= float(max_price))

    products = query.all()

    result = []
    for p in products:
        result.append({
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "stock": p.stock
        })

    return {"products": result}

@app.route('/my-orders', methods=['GET'])
@jwt_required()
def my_orders():
    user_id = int(get_jwt_identity())

    orders = Orders.query.filter_by(user_id=user_id).all()

    result = []

    for order in orders:
        items = OrderItems.query.filter_by(order_id=order.id).all()
        order_products = []

        for item in items:
            product = Products.query.get(item.product_id)
            if product:
                order_products.append({
                    "product_id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "quantity": item.quantity
                })

        result.append({
            "order_id": order.id,
            "total_price": order.total_price,
            "status": order.status,
            "created_at": str(order.created_at),
            "items": order_products
        })

    return {"orders": result}

if __name__ == '__main__':
    app.run(debug=True)