import mysql.connector
import configparser
from flask import Flask, render_template, flash, redirect, url_for, request
from flask_mysqldb import MySQL
from validate_email_address import validate_email
from wtforms import Form, validators, StringField, FloatField, IntegerField, DateField, SelectField
from datetime import datetime
import MySQLdb
import urllib.parse
import requests

app = Flask(__name__)

# Loading configuration 
config = configparser.ConfigParser()
config.read('config.ini')

# MySQL Config
app.config['MYSQL_HOST'] = config['database']['host']
app.config['MYSQL_USER'] = config['database']['user']
app.config['MYSQL_PASSWORD'] = config['database']['password']
app.config['MYSQL_PORT'] = config.getint('database', 'port')
app.config['MYSQL_DB'] = config['database']['db']
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.secret_key = config['app']['secret_key']

mysql = MySQL(app)


# Home
@app.route('/')
def index():
    return render_template('home.html')

# Books
@app.route('/books')
def books():
    with mysql.connection.cursor() as cursor:
        cursor.execute("SELECT id,title,author,total_quantity,available_quantity FROM books")
        books = cursor.fetchall()
    
    if books:
        return render_template('books.html', books=books)
    else:
        return render_template('books.html', warning='No Books Found')
    cur.close()

# Define Add-Book-Form
class AddBook(Form):
    id = StringField(
        'Book ID', [validators.Length(min=1, max=11)])
    title = StringField(
        'Title', [validators.Length(min=2, max=255)])
    author = StringField(
        'Author', [validators.Length(min=2, max=255)])
    language_code = StringField(
        'Language', [validators.Length(min=1, max=10)])
    total_quantity = IntegerField(
        'Total Number of Books', [validators.NumberRange(min=1, max=100)])
    isbn = StringField(
        'ISBN', [validators.Length(min=10, max=10)])
    isbn13 = StringField(
        'ISBN13', [validators.Length(min=13, max=13)])
    average_rating = FloatField(
        'Average Rating', [validators.NumberRange(min=0, max=5)])
    num_pages = IntegerField(
        'Number of Pages', [validators.NumberRange(min=1)])
    ratings_count = IntegerField(
        'Number of Ratings', [validators.NumberRange(min=0)])
    text_reviews_count = IntegerField(
        'Number of Text Reviews', [validators.NumberRange(min=0)])
    publisher = StringField(
        'Publisher Name ', [validators.Length(min=2, max=255)])
    publication_date = DateField(
        'Publication Date', [validators.InputRequired()])
    
    
# Add Book Route
@app.route('/book_add', methods=['GET', 'POST'])
def book_add():
    form = AddBook(request.form)
    if request.method == 'POST' and form.validate():
        cur = mysql.connection.cursor()

        result = cur.execute(
            "SELECT id FROM books WHERE id=%s", [form.id.data])
        book = cur.fetchone()
        if(book):
            error = 'Book with that ID already exists'
            return render_template('book_add.html', form=form, error=error)
        cur.execute("INSERT INTO books (id,title,author,average_rating,isbn,isbn13,language_code,num_pages,ratings_count,text_reviews_count,publication_date,publisher,total_quantity,available_quantity) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", [
            form.id.data,
            form.title.data,
            form.author.data,
            form.average_rating.data,
            form.isbn.data,
            form.isbn13.data,
            form.language_code.data,
            form.num_pages.data,
            form.ratings_count.data,
            form.text_reviews_count.data,
            form.publication_date.data,
            form.publisher.data,
            form.total_quantity.data,
            form.total_quantity.data
        ])

        mysql.connection.commit()
        cur.close()

        flash("New Book Added", "success")

        return redirect(url_for('books'))

    return render_template('book_add.html', form=form)




# Define Import-Books-Form
class ImportBooks(Form):
    no_of_books = IntegerField(
        'Number of Books', [validators.NumberRange(min=1)])
    title = StringField(
        'Title', [validators.Optional(), validators.Length(min=1, max=255)])
    author = StringField(
        'Author', [validators.Optional(), validators.Length(min=1, max=255)])
    
    


# Import Books 
@app.route('/book_import', methods=['GET', 'POST'])
def book_import():
    form = ImportBooks(request.form)

    if request.method == 'POST' and form.validate():
        cur = mysql.connection.cursor()

        no_of_books_imported = 0
        repeated_book_ids = []

        # Defining base URL 
        base_url = 'https://frappe.io/api/method/frappe-library?'

        # parameters for the API request
        parameters = {
            'page': 1,
            'title': form.title.data,
            'author': form.author.data,
        }

        while no_of_books_imported < form.no_of_books.data:
            r = requests.get(base_url + urllib.parse.urlencode(parameters))
            res = r.json()

            # Break if message is empty
            if not res.get('message'):
                break

            for book in res['message']:
                result = cur.execute("SELECT id FROM books WHERE id=%s", [book['bookID']])
                book_found = cur.fetchone()
                if not book_found:
                    num_pages = book.get('num_pages')
                    publication_date_str = book.get('publication_date', '')  # Assuming it's a string

                    try:
                        if publication_date_str:
                            date_obj = datetime.strptime(publication_date_str, '%m/%d/%Y')
                            formatted_date = date_obj.strftime('%Y-%m-%d')
                        else:
                            formatted_date = None  
                        
                        # SQL Query 
                        cur.execute("INSERT INTO books (id, title, author, average_rating, isbn, isbn13, language_code, num_pages, ratings_count, text_reviews_count, publication_date, publisher, total_quantity, available_quantity) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", [
                            book['bookID'],
                            book['title'],
                            book['authors'],
                            book['average_rating'],
                            book['isbn'],
                            book['isbn13'],
                            book['language_code'],
                            num_pages,
                            book['ratings_count'],
                            book['text_reviews_count'],
                            formatted_date,  
                            book['publisher'],
                            form.no_of_books.data,
                            form.no_of_books.data
                        ])
                        no_of_books_imported += 1
                        if no_of_books_imported == form.no_of_books.data:
                            break
                    except ValueError:
                        formatted_date = None
                else:
                    repeated_book_ids.append(book['bookID'])

            parameters['page'] += 1 

        mysql.connection.commit()
        cur.close()

        # Flash Message
        msg = f"{no_of_books_imported}/{form.no_of_books.data} books have been imported."
        msgType = 'success'
        if no_of_books_imported != form.no_of_books.data:
            msgType = 'warning'
            if repeated_book_ids:
                msg += f" {len(repeated_book_ids)} books were found with already existing IDs."
            else:
                msg += f" {form.no_of_books.data - no_of_books_imported} matching books were not found."
        flash(msg, msgType)

        return redirect(url_for('books'))

    return render_template('book_import.html', form=form)

# Define Search-Form
class SearchBook(Form):
    title = StringField('Title', [validators.Length(min=1, max=255)])
    author = StringField('Author', [validators.Length(min=1, max=255)])


# Search
@app.route('/book_search', methods=['GET', 'POST'])
def book_search():
    form = SearchBook(request.form)

    if request.method == 'POST' and form.validate():
        cur = mysql.connection.cursor()
        title = '%'+form.title.data+'%'
        author = '%'+form.author.data+'%'
        result = cur.execute(
            "SELECT * FROM books WHERE title LIKE %s OR author LIKE %s", [title, author])
        books = cur.fetchall()
        cur.close()

        # Flash Message
        if result <= 0:
            msg = 'No Results Found'
            return render_template('book_search.html', form=form, warning=msg)

        flash("Results Found", "success")
        
        return render_template('book_search.html', form=form, books=books)

    return render_template('book_search.html', form=form)
        

# Book deatils
@app.route('/book/<string:id>')
def viewbook(id):
    with mysql.connection.cursor() as cursor:
        cursor.execute("SELECT * FROM books WHERE id=%s", [id])
        book = cursor.fetchone()

    if book:
        return render_template('book_details.html', book=book)
    else:
        return render_template('book_details.html', warning='This Book Does Not Exist')

    cur.close()

# Edit Book Route
@app.route('/book_edit/<string:id>', methods=['GET', 'POST'])
def edit_book(id):
    form = AddBook(request.form)

    with mysql.connection.cursor() as cursor:
        result = cursor.execute("SELECT * FROM books WHERE id=%s", [id])
        book = cursor.fetchone()

        if request.method == 'POST' and form.validate():
            if(form.id.data != id):
                result = cursor.execute(
                    "SELECT id FROM books WHERE id=%s", [form.id.data])
                existing_book = cursor.fetchone()
                if(existing_book):
                    error = 'Book with that ID already exists'
                    return render_template('book_edit.html', form=form, error=error, book=form.data)

            # Calculate new available_quantity 
            available_quantity = book['available_quantity'] + \
                (form.total_quantity.data - book['total_quantity'])

            #  SQL Query 
            cursor.execute("UPDATE books SET id=%s,title=%s,author=%s,average_rating=%s,isbn=%s,isbn13=%s,language_code=%s,num_pages=%s,ratings_count=%s,text_reviews_count=%s,publication_date=%s,publisher=%s,total_quantity=%s,available_quantity=%s WHERE id=%s", [
                form.id.data,
                form.title.data,
                form.author.data,
                form.average_rating.data,
                form.isbn.data,
                form.isbn13.data,
                form.language_code.data,
                form.num_pages.data,
                form.ratings_count.data,
                form.text_reviews_count.data,
                form.publication_date.data,
                form.publisher.data,
                form.total_quantity.data,
                available_quantity,
                id])

            mysql.connection.commit()

            flash("Book Updated", "success")

            return redirect(url_for('books'))

    return render_template('book_edit.html', form=form, book=book)


# Delete Book Route
@app.route('/delete_book/<string:id>', methods=['POST'])
def delete_book(id):
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("DELETE FROM books WHERE id=%s", [id])

            mysql.connection.commit()

        flash("Book Deleted", "success")
    except (MySQLdb.Error, MySQLdb.Warning) as e:
        print(e)

        flash("Book could not be deleted", "danger")
        flash(str(e), "danger")

        return redirect(url_for('books'))

    return redirect(url_for('books'))


# Members Route
@app.route('/members')
def members():
    try:
        with mysql.connection.cursor() as cursor:
            result = cursor.execute("SELECT * FROM members")
            members = cursor.fetchall()

            if result > 0:
                return render_template('members.html', members=members)
            else:
                return render_template('members.html', warning='No Members Found')
    except (MySQLdb.Error, MySQLdb.Warning) as e:
        
        # Handle database errors
        print(e)
        flash("Error: Could not fetch members", "danger")

    return redirect(url_for('members'))


# Details  Member
@app.route('/member_details/<string:id>')
def member_details(id):
    try:
        with mysql.connection.cursor() as cursor:

            result = cursor.execute("SELECT * FROM members WHERE id=%s", [id])
            member = cursor.fetchone()

            
            if result > 0:
                return render_template('member_details.html', member=member)
            else:
                msg = 'This Member Does Not Exist'
                return render_template('member_details.html', warning=msg)
    except (MySQLdb.Error, MySQLdb.Warning) as e:
        
        print(e)
        flash("Error: Could not fetch member details", "danger")

    return redirect(url_for('members')) 


# Define Add-Member-Form
class AddMember(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    email = StringField('Email', [validators.length(min=6, max=50)])
    ph_no= StringField('Phone Number',[validators.Length(min=10 ,max=10)] )

# Add Member Route
@app.route('/member_add', methods=['GET', 'POST'])
def member_add():
    try:
        form = AddMember(request.form)

        if request.method == 'POST' and form.validate():
            name = form.name.data
            email = form.email.data
            ph_no = form.ph_no.data

            if not validate_email(email):
                flash("Invalid email address", "danger")
                return render_template('member_add.html', form=form)

            with mysql.connection.cursor() as cursor:
                # SQL Query
                cursor.execute(
                    "INSERT INTO members (name, email, ph_no) VALUES (%s, %s, %s)", (name, email, ph_no))

                mysql.connection.commit()

            flash("New Member Added", "success")

            return redirect(url_for('members'))

        return render_template('member_add.html', form=form)

    except (MySQLdb.Error, MySQLdb.Warning) as e:
        print(e)
        flash("Error: Could not add member", "danger")

    return redirect(url_for('members'))

# Edit Member 
@app.route('/member_edit/<string:id>', methods=['GET', 'POST'])
def member_edit(id):
    try:
        cur = mysql.connection.cursor()

        if request.method == 'POST':
            form = AddMember(request.form)

            if form.validate():
                name = form.name.data
                email = form.email.data
                ph_no = form.ph_no.data

                # SQL Query 
                cur.execute(
                    "UPDATE members SET name=%s, email=%s, ph_no=%s WHERE id=%s", (name, email, ph_no, id))

                
                mysql.connection.commit()
                cur.close()

                flash("Member Updated", "success")

                return redirect(url_for('members'))
            else:
                flash("Form validation failed. Please check your inputs.", "danger")

        #  SQL Query 
        cur.execute("SELECT name, email, ph_no FROM members WHERE id=%s", [id])
        member = cur.fetchone()

        if member:
            form = AddMember(request.form)
            form.name.data = member['name']
            form.email.data = member['email']
            form.ph_no.data = member['ph_no']
        else:
            flash("Member not found", "danger")
            return redirect(url_for('members'))

        return render_template('member_edit.html', form=form, member=member)

    except (MySQLdb.Error, MySQLdb.Warning) as e:
        print(e)
        flash("Error: Could not edit member", "danger")

    return redirect(url_for('members'))

# Delete Member 
@app.route('/delete_member/<string:id>', methods=['POST'])
def delete_member(id):
    try:
        with mysql.connection.cursor() as cursor:
            cursor.execute("DELETE FROM members WHERE id=%s", [id])

            mysql.connection.commit()

        flash("Member Deleted", "success")

    except (MySQLdb.Error, MySQLdb.Warning) as e:
        print(e)
        flash("Error: Member could not be deleted", "danger")
        flash(str(e), "danger")
        return redirect(url_for('members'))

    return redirect(url_for('members'))


# Transactions 
@app.route('/transactions')
def transactions():
    try:
        cur = mysql.connection.cursor()

        # SQL Query
        result = cur.execute("SELECT * FROM transactions")
        transactions = cur.fetchall()

        cur.close()

        for transaction in transactions:
            for key, value in transaction.items():
                if value is None:
                    transaction[key] = "-"

        if result > 0:
            return render_template('transactions.html', transactions=transactions)
        else:
            msg = 'No Transactions Found'
            return render_template('transactions.html', warning=msg)
    except (MySQLdb.Error, MySQLdb.Warning) as e:
        print(e)
        flash("Error: Could not fetch transactions", "danger")

    return redirect(url_for('transactions'))


# Define Issue-Book-Form
class IssueBook(Form):
    book_id = SelectField('Book ID', choices=[])
    member_id = SelectField('Member ID', choices=[])
    per_day_fee = FloatField('Per Day Renting Fee', [
                             validators.NumberRange(min=1)])



# Issue Book Route
@app.route('/book_issue', methods=['GET', 'POST'])
def book_issue():
    try:
        form = IssueBook(request.form)
        cur = mysql.connection.cursor()

        book_ids_list = []
        member_ids_list = []

        cur.execute("SELECT id, title FROM books")
        books = cur.fetchall()
        for book in books:
            t = (book['id'], book['title'])
            book_ids_list.append(t)

        cur.execute("SELECT id, name FROM members")
        members = cur.fetchall()
        for member in members:
            t = (member['id'], member['name'])
            member_ids_list.append(t)

        form.book_id.choices = book_ids_list
        form.member_id.choices = member_ids_list

        if request.method == 'POST' and form.validate():

            cur.execute("SELECT available_quantity FROM books WHERE id=%s", [
                form.book_id.data])
            result = cur.fetchone()
            available_quantity = result['available_quantity']

            if available_quantity < 1:
                error = 'No copies of this book are available to be rented'
                return render_template('book_issue.html', form=form, error=error)

            # SQL Query 
            cur.execute("INSERT INTO transactions (book_id, member_id, per_day_fee) VALUES (%s, %s, %s)", [
                form.book_id.data,
                form.member_id.data,
                form.per_day_fee.data,
            ])

            cur.execute(
                "UPDATE books SET available_quantity=available_quantity-1, rented_count=rented_count+1 WHERE id=%s", [form.book_id.data])

            mysql.connection.commit()

            flash("Book Issued", "success")

            return redirect(url_for('transactions'))

    except (MySQLdb.Error, MySQLdb.Warning) as e:
        print(e)
        flash("Error: Could not issue the book", "danger")

    finally:
        if 'cur' in locals() or 'cur' in globals():
            cur.close()
    return render_template('book_issue.html', form=form)

# Define Issue-Book-Form
class ReturnBook(Form):
    amount_paid = FloatField('Amount Paid', [validators.NumberRange(min=0)])


# Return Book 
@app.route('/book_return/<string:transaction_id>', methods=['GET', 'POST'])
def book_return(transaction_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM transactions WHERE id=%s", [transaction_id])
        transaction = cur.fetchone()

        # Calc Total Charge
        date = datetime.now()
        difference = date - transaction['borrowed_on']
        difference = difference.days
        total_charge = difference * transaction['per_day_fee']

        form = ReturnBook(request.form)

        if request.method == 'POST':
            if form.validate():
                # Calc debt 
                transaction_debt = total_charge - form.amount_paid.data

                # Check outstanding_debt + transaction_debt exceeds Rs.500
                cur.execute("SELECT outstanding_debt, amount_spent FROM members WHERE id=%s", [
                    transaction['member_id']])
                result = cur.fetchone()
                outstanding_debt = result['outstanding_debt'] or 0
                amount_spent = result['amount_spent'] or 0

                if (outstanding_debt + transaction_debt >= 500):
                    error = 'Outstanding Debt Cannot Exceed Rs.500'
                    return render_template('book_return.html', form=form, error=error)

                cur.execute("UPDATE transactions SET returned_on=%s, total_charge=%s, amount_paid=%s WHERE id=%s", [
                    date,
                    total_charge,
                    form.amount_paid.data,
                    transaction_id
                ])

                cur.execute("UPDATE members SET outstanding_debt=%s, amount_spent=%s WHERE id=%s", [
                    outstanding_debt + transaction_debt,
                    amount_spent + form.amount_paid.data,
                    transaction['member_id']
                ])

                cur.execute(
                    "UPDATE books SET available_quantity=available_quantity+1 WHERE id=%s", [transaction['book_id']])


                mysql.connection.commit()

                flash("Book Returned", "success")

                return redirect(url_for('transactions'))
            else:
                flash("Form validation failed. Please check your inputs.", "danger")

        return render_template('book_return.html', total_charge=total_charge, difference=difference, transaction=transaction, form=form)

    except (MySQLdb.Error, MySQLdb.Warning) as e:
        print(e)
        flash("Error: Could not return the book", "danger")

    finally:
        if 'cur' in locals() or 'cur' in globals():
            cur.close()



if __name__ == '__main__':
    app.secret_key = "secret"
    app.run(debug=True)
