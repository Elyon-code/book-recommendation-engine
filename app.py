# Book Recommendation Engine - Built with Flask and SQLAlchemy

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

if __name__ == '__main__':
    app.run(debug=True)