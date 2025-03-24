# Book Recommendation Engine - Built with Flask and SQLAlchemy

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from sqlalchemy import func

# Add after app initialization

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

# ---- Collaborative Filtering Logic ----
def get_similar_users(user_id, min_common_books=3):
    """Find users with similar ratings patterns"""
    current_user_ratings = Rating.query.filter_by(user_id=user_id).all()
    current_books = {r.book_id: r.score for r in current_user_ratings}

    all_users = User.query.filter(User.id != user_id).all()
    similarities = []

    for user in all_users:
        user_ratings = {r.book_id: r.score for r in user.ratings}
        common_books = set(current_books.keys()) & set(user_ratings.keys())

        if len(common_books) >= min_common_books:
            # Calculate Pearson correlation
            sum1 = sum(current_books[b] for b in common_books)
            sum2 = sum(user_ratings[b] for b in common_books)
            sum1_sq = sum(pow(current_books[b], 2) for b in common_books)
            sum2_sq = sum(pow(user_ratings[b], 2) for b in common_books)
            p_sum = sum(current_books[b] * user_ratings[b] for b in common_books)
            
            n = len(common_books)
            numerator = p_sum - (sum1 * sum2 / n)
            denominator = ((sum1_sq - pow(sum1, 2)/n) * (sum2_sq - pow(sum2, 2)/n)) ** 0.5
            
            if denominator != 0:
                similarity = numerator / denominator
                similarities.append((user.id, similarity))

    # Return top 5 similar users
    return sorted(similarities, key=lambda x: x[1], reverse=True)[:5]

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

@app.route('/books/<int:id>', methods=['PUT'])
def update_book(id):
    book = Book.query.get_or_404(id)
    data = request.get_json()
    if 'title' in data:
        book.title = data['title']
    if 'author' in data:
        book.author = data['author']
    if 'genre' in data:
        book.genre = data['genre']
    db.session.commit()
    return {"message": "Book updated successfully"}, 200

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

@app.route('/ratings')
def get_ratings():
    ratings = Rating.query.all()
    rating_list = [{
        "id": rating.id,
        "user_id": rating.user_id,
        "book_id": rating.book_id,
        "score": rating.score
    } for rating in ratings]
    return {"ratings": rating_list}

@app.route('/books/<int:id>/average-rating')
def get_average_rating(id):
    book = Book.query.get_or_404(id)
    average_rating = db.session.query(db.func.avg(Rating.score)).filter_by(book_id=id).scalar()
    return {"book_id": book.id, "average_rating": round(float(average_rating or 0), 2)}

@app.route('/books/count')
def get_book_count():
    count = Book.query.count()
    return {"total_books": count}

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

@app.route('/users')
def get_users():
    users = User.query.all()
    user_list = [{
        "id": user.id,
        "username": user.username,
        "email": user.email
    } for user in users]
    return {"users": user_list}

@app.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return {"message": "User deleted successfully"}, 200

# New recommendation endpoint
@app.route('/recommend/<int:user_id>')
@jwt_required()
def get_recommendations(user_id):
    # Check if user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get similar users
    similar_users = get_similar_users(user_id)
    if not similar_users:
        return jsonify({"message": "Not enough data for recommendations. Rate more books!"}), 200

    # Get books rated by similar users (that current user hasn't rated)
    similar_user_ids = [u[0] for u in similar_users]
    user_rated_books = {r.book_id for r in user.ratings}

    recommended_books = db.session.query(Book).join(Rating).filter(
        Rating.user_id.in_(similar_user_ids),
        ~Book.id.in_(user_rated_books)
    ).group_by(Book.id).order_by(db.desc(db.func.avg(Rating.score))).limit(10).all()

    return jsonify({
        "recommendations": [{
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": book.genre
        } for book in recommended_books]
    })

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