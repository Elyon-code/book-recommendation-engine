# Book Recommendation Engine - Built with Flask and SQLAlchemy

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
# Add after app initialization
.

app = Flask(__name__)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)


# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = "your-super-secret-key"  # Change in production!
jwt = JWTManager(app)

# Initialize the database
db = SQLAlchemy(app)

# Define the Book model
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<Book {self.title}>"
    
# Add after Book model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    ratings = db.relationship('Rating', backref='book', lazy=True)

# Add new model
class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)

# Create the database and tables
with app.app_context():
    db.create_all()

    # Check if the database is empty
    is_empty = not Book.query.first()
    print("Is database empty?", is_empty)

    if is_empty:
        # Add sample books
        book1 = Book(title="The Great Gatsby", author="F. Scott Fitzgerald", genre="Classic")
        book2 = Book(title="To Kill a Mockingbird", author="Harper Lee", genre="Fiction")
        book3 = Book(title="1984", author="George Orwell", genre="Dystopian")
        book4 = Book(title="Pride and Prejudice", author="Jane Austen", genre="Romance")
        book5 = Book(title="The Catcher in the Rye", author="J.D. Salinger", genre="Coming-of-Age")

        # Add books to the session
        db.session.add(book1)
        db.session.add(book2)
        db.session.add(book3)
        db.session.add(book4)
        db.session.add(book5)

        # Commit the changes
        db.session.commit()
        print("Sample books added to the database!")

# Home route
@app.route('/')
def home():
    return "Hello, World! Welcome to the Book Recommendation Engine!"


from flask import request  # Add this import at the top

# Update the existing /books route
@app.route('/books')
def get_books():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    books = Book.query.paginate(page=page, per_page=per_page)
    book_list = [{
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "genre": book.genre
    } for book in books.items]
    return {
        "books": book_list,
        "total_pages": books.pages,
        "current_page": page
    }

from sqlalchemy import func  # Add this import at the top

@app.route('/books/random')
def get_random_books():
    random_books = Book.query.order_by(func.random()).limit(3).all()
    book_list = [{
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "genre": book.genre
    } for book in random_books]
    return {"recommendations": book_list}

@app.route('/books/<int:id>')
def get_book(id):
    book = Book.query.get_or_404(id)
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "genre": book.genre
    }

@app.route('/books/genre/<string:genre>')
def get_books_by_genre(genre):
    books = Book.query.filter_by(genre=genre).all()
    if not books:
        return {"error": "No books found for this genre"}, 404
    book_list = []
    for book in books:
        book_list.append({
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": book.genre
        })
    return {"books": book_list}

@app.errorhandler(404)
def not_found(error):
    return {"error": "Resource not found"}, 404

@app.route('/health')
def health_check():
    return {"status": "healthy", "message": "Book Recommendation API is running"}, 200

# Add new route
@app.route('/register', methods=['POST'])
@limiter.limit("10/hour")
def register_user():
    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data:
        return {"error": "Missing required fields"}, 400
    if User.query.filter_by(username=data['username']).first():
        return {"error": "Username already exists"}, 409
    if User.query.filter_by(email=data['email']).first():
        return {"error": "Email already registered"}, 409
    new_user = User(
        username=data['username'],
        email=data['email']
    )
    db.session.add(new_user)
    db.session.commit()
    return {"message": "User created successfully"}, 201

# New recommendation endpoint
@app.route('/recommend/<int:user_id>')
@jwt_required()
def get_recommendations(user_id):
    user_ratings = Rating.query.filter_by(user_id=user_id).all()
    if not user_ratings:
        return {"message": "Rate books to get recommendations"}, 400
    
    # Simple logic: Recommend books from most-rated genre
    favorite_genre = db.session.query(
        Book.genre,
        db.func.count(Rating.id).label('total')
    ).join(Rating).group_by(Book.genre).order_by(db.desc('total')).first()[0]

    recommended_books = Book.query.filter_by(genre=favorite_genre).limit(5).all()
    return {"recommendations": [b.title for b in recommended_books]}

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if not user:
        return {"error": "Invalid credentials"}, 401
    access_token = create_access_token(identity=user.id)
    return {"access_token": access_token}, 200



if __name__ == '__main__':
    app.run(debug=True)