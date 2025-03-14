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

if __name__ == '__main__':
    app.run(debug=True)