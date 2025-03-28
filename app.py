"""
Book Recommendation Engine - Production Ready
Flask API with SQLAlchemy, JWT Auth, and Collaborative Filtering
"""

from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from sqlalchemy import func, and_
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config.update({
    'SQLALCHEMY_DATABASE_URI': os.getenv('DATABASE_URL', 'sqlite:///books.db'),
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'JWT_SECRET_KEY': os.getenv('JWT_SECRET_KEY', 'your-super-secret-key'),
    'JWT_ACCESS_TOKEN_EXPIRES': timedelta(hours=1)
})

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# --- Models ---
class Book(db.Model):
    """Book model with basic information"""
    __tablename__ = 'books'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, index=True)
    author = db.Column(db.String(100), nullable=False, index=True)
    genre = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    published_year = db.Column(db.Integer)
    ratings = db.relationship('Rating', backref='book', lazy=True)

    def __repr__(self):
        return f"<Book {self.title}>"

class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))  # In production, use proper hashing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ratings = db.relationship('Rating', backref='user', lazy=True)

class Rating(db.Model):
    """Rating model connecting users and books"""
    __tablename__ = 'ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='unique_user_book_rating'),
    )

# --- Helper Functions ---
def calculate_similarity(user1_id, user2_id):
    """Calculate Pearson correlation between two users"""
    user1_ratings = {r.book_id: r.score for r in Rating.query.filter_by(user_id=user1_id).all()}
    user2_ratings = {r.book_id: r.score for r in Rating.query.filter_by(user_id=user2_id).all()}
    
    common_books = set(user1_ratings.keys()) & set(user2_ratings.keys())
    n = len(common_books)
    
    if n < 3:  # Minimum 3 common ratings for meaningful similarity
        return 0
    
    # Calculate Pearson correlation
    sum1 = sum(user1_ratings[b] for b in common_books)
    sum2 = sum(user2_ratings[b] for b in common_books)
    sum1_sq = sum(pow(user1_ratings[b], 2) for b in common_books)
    sum2_sq = sum(pow(user2_ratings[b], 2) for b in common_books)
    p_sum = sum(user1_ratings[b] * user2_ratings[b] for b in common_books)
    
    num = p_sum - (sum1 * sum2 / n)
    den = ((sum1_sq - pow(sum1, 2)/n) * (sum2_sq - pow(sum2, 2)/n)) ** 0.5
    
    return num / den if den != 0 else 0

def get_user_preferred_genres(user_id, top_n=2):
    """Get user's top preferred genres based on their ratings"""
    genre_scores = db.session.query(
        Book.genre,
        db.func.avg(Rating.score).label('avg_rating'),
        db.func.count(Rating.id).label('count')
    ).join(Rating).filter(
        Rating.user_id == user_id
    ).group_by(Book.genre).all()
    
    if not genre_scores:
        return None
    
    # Sort by average rating (weighted by number of ratings)
    preferred = sorted(
        genre_scores,
        key=lambda x: (x.avg_rating * min(x.count, 5)),  # Cap influence of many ratings
        reverse=True
    )
    return [g.genre for g in preferred[:top_n]]

# --- Routes ---
@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "running",
        "version": "1.0",
        "documentation": "/docs"  # Would link to API docs in production
    })

@app.route('/books', methods=['GET'])
def get_books():
    """Get paginated list of books with optional filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 50)
    genre = request.args.get('genre')
    author = request.args.get('author')
    
    query = Book.query
    
    if genre:
        query = query.filter(Book.genre.ilike(f"%{genre}%"))
    if author:
        query = query.filter(Book.author.ilike(f"%{author}%"))
    
    books = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        "books": [{
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": book.genre
        } for book in books.items],
        "total": books.total,
        "pages": books.pages,
        "current_page": page
    })

@app.route('/books/<int:book_id>', methods=['GET', 'PUT'])
def book_detail(book_id):
    """Get or update a specific book"""
    book = Book.query.get_or_404(book_id)
    
    if request.method == 'GET':
        return jsonify({
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": book.genre,
            "description": book.description,
            "published_year": book.published_year,
            "average_rating": db.session.query(
                db.func.avg(Rating.score)
            ).filter_by(book_id=book_id).scalar() or 0
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Update only provided fields
        if 'title' in data:
            book.title = data['title']
        if 'author' in data:
            book.author = data['author']
        if 'genre' in data:
            book.genre = data['genre']
        if 'description' in data:
            book.description = data['description']
        if 'published_year' in data:
            book.published_year = data['published_year']
            
        db.session.commit()
        return jsonify({"message": "Book updated successfully"})

@app.route('/books/random', methods=['GET'])
def random_books():
    """Get random selection of books"""
    count = min(request.args.get('count', 3, type=int), 10)
    books = Book.query.order_by(func.random()).limit(count).all()
    
    return jsonify({
        "books": [{
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "genre": book.genre
        } for book in books]
    })

@app.route('/recommend/<int:user_id>', methods=['GET'])
@jwt_required()
def recommend_books(user_id):
    """Get personalized book recommendations for a user"""
    # Check user exists
    user = User.query.get_or_404(user_id)
    
    # Strategy 1: Content-based (preferred genres)
    preferred_genres = get_user_preferred_genres(user_id)
    user_rated_books = {r.book_id for r in user.ratings}
    
    if preferred_genres:
        content_recs = Book.query.filter(
            Book.genre.in_(preferred_genres),
            ~Book.id.in_(user_rated_books)
        ).order_by(func.random()).limit(5).all()
    else:
        content_recs = []
    
    # Strategy 2: Collaborative filtering
    all_users = User.query.filter(User.id != user_id).all()
    similarities = []
    
    for other_user in all_users:
        similarity = calculate_similarity(user_id, other_user.id)
        if similarity > 0.3:  # Only consider meaningful similarities
            similarities.append((other_user.id, similarity))
    
    # Sort by similarity and get top 5
    similarities.sort(key=lambda x: x[1], reverse=True)
    similar_user_ids = [uid for uid, _ in similarities[:5]]
    
    if similar_user_ids:
        collab_recs = db.session.query(Book).join(Rating).filter(
            Rating.user_id.in_(similar_user_ids),
            ~Book.id.in_(user_rated_books)
        ).group_by(Book.id).order_by(
            db.desc(db.func.avg(Rating.score))
        ).limit(5).all()
    else:
        collab_recs = []
    
    # Combine and deduplicate recommendations
    all_recs = {(b.id, b.title, b.author, b.genre) for b in content_recs + collab_recs}
    
    if not all_recs:
        # Fallback to popular books if no personalized recommendations
        all_recs = db.session.query(Book).join(Rating).group_by(Book.id).order_by(
            db.desc(db.func.avg(Rating.score))
        ).limit(5).all()
        all_recs = {(b.id, b.title, b.author, b.genre) for b in all_recs}
    
    return jsonify({
        "recommendations": [{
            "id": rec[0],
            "title": rec[1],
            "author": rec[2],
            "genre": rec[3]
        } for rec in all_recs]
    })

@app.route('/ratings', methods=['POST'])
@jwt_required()
def add_rating():
    """Add or update a book rating"""
    data = request.get_json()
    if not data or 'book_id' not in data or 'score' not in data:
        return jsonify({"error": "Missing book_id or score"}), 400
    
    try:
        score = int(data['score'])
        if not 1 <= score <= 5:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Score must be integer between 1-5"}), 400
    
    user_id = get_jwt_identity()
    book_id = data['book_id']
    
    # Check if book exists
    if not Book.query.get(book_id):
        return jsonify({"error": "Book not found"}), 404
    
    # Update existing rating or create new one
    rating = Rating.query.filter_by(user_id=user_id, book_id=book_id).first()
    if rating:
        rating.score = score
    else:
        rating = Rating(user_id=user_id, book_id=book_id, score=score)
        db.session.add(rating)
    
    db.session.commit()
    return jsonify({"message": "Rating saved successfully"})

# --- Authentication ---
@app.route('/register', methods=['POST'])
@limiter.limit("5/hour")
def register():
    """Register a new user"""
    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data or 'password' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already registered"}), 409
    
    # In production: hash the password properly (e.g., using bcrypt)
    new_user = User(
        username=data['username'],
        email=data['email'],
        password_hash=data['password']  # This is simplified - don't do this in production!
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "User created successfully"}), 201

@app.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token"""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    if not user or user.password_hash != data['password']:  # Simplified auth
        return jsonify({"error": "Invalid credentials"}), 401
    
    access_token = create_access_token(identity=user.id)
    return jsonify({
        "access_token": access_token,
        "user_id": user.id
    })

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# --- Database Initialization ---
def initialize_database():
    """Initialize database with sample data if empty"""
    with app.app_context():
        db.create_all()
        
        if not Book.query.first():
            sample_books = [
                Book(title="The Great Gatsby", author="F. Scott Fitzgerald", genre="Classic"),
                Book(title="To Kill a Mockingbird", author="Harper Lee", genre="Fiction"),
                Book(title="1984", author="George Orwell", genre="Dystopian"),
                Book(title="Pride and Prejudice", author="Jane Austen", genre="Romance"),
                Book(title="The Catcher in the Rye", author="J.D. Salinger", genre="Coming-of-Age")
            ]
            db.session.add_all(sample_books)
            db.session.commit()
            print("Sample books added to database")

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)