#from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory
#from datetime import datetime
#import os, subprocess


# Standard Library Imports
import asyncio
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

# Third-Party Imports
import fitz  # PyMuPDF
import pytesseract
import requests
from PIL import Image
from telegram import Bot
from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory

app = Flask(__name__)


UPLOAD_FOLDER = "/home/debian/bookmark_bot/epubs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure EPUB folder exists

TRANSFER_FOLDER = "/home/debian/bookmark_bot/transfers"
os.makedirs(TRANSFER_FOLDER, exist_ok=True)

# Allowed file extensions (excluding scripts like .sh, .py, etc.)
EXCLUDED_EXTENSIONS = {"sh", "py", "exe", "bat", "cmd", "js", "php", "pl", "rb"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() not in EXCLUDED_EXTENSIONS

@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    message = None
    if request.method == "POST":
        if "file" not in request.files:
            message = "No file part."
        else:
            file = request.files["file"]
            if file.filename == "":
                message = "No selected file."
            elif allowed_file(file.filename):
                file.save(os.path.join(TRANSFER_FOLDER, file.filename))
                message = "File uploaded successfully."
            else:
                message = "File type not allowed."
    
    # List all files excluding scripts
    files = [f for f in os.listdir(TRANSFER_FOLDER) if allowed_file(f)]
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>File Transfer</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f4f4f4; }
            button { padding: 5px 10px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>File Transfer</h1>
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="file" required>
            <button type="submit">Upload</button>
        </form>
        {% if message %}
            <p><strong>{{ message }}</strong></p>
        {% endif %}
        <h2>Available Files</h2>
        <table>
            <tr>
                <th>Filename</th>
                <th>Download</th>
                <th>Delete</th>
            </tr>
            {% for file in files %}
            <tr>
                <td>{{ file }}</td>
                <td><a href="{{ url_for('download_transfer', filename=file) }}"><button>Download</button></a></td>
                <td><a href="{{ url_for('delete_transfer', filename=file) }}"><button>Delete</button></a></td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """, files=files, message=message)

@app.route("/transfer/download/<filename>")
def download_transfer(filename):
    return send_from_directory(TRANSFER_FOLDER, filename, as_attachment=True)

@app.route("/transfer/delete/<filename>")
def delete_transfer(filename):
    file_path = os.path.join(TRANSFER_FOLDER, filename)
    if os.path.exists(file_path) and allowed_file(filename):
        os.remove(file_path)
    return redirect(url_for("transfer"))

def convert_webpage_to_epub(url):
    """Runs the conversion script for the given URL."""
    subprocess.run(["python3", "/home/debian/bookmark_bot/web_to_epub.py", url], check=True)

@app.route("/epub", methods=["GET", "POST"])
def index_epub():
    if request.method == "POST":
        url = request.form["url"]
        if url:
            convert_webpage_to_epub(url)
    
    # Get list of EPUB files
    epub_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".epub")]
    
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Web to EPUB Converter</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f4f4f4; }
            button { padding: 5px 10px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>Web to EPUB Converter</h1>
        <form method="POST">
            <input type="text" name="url" placeholder="Enter website URL" required>
            <button type="submit">Convert</button>
        </form>

        <h2>Converted EPUB Files</h2>
        <table>
            <tr>
                <th>Filename</th>
                <th>Download</th>
                <th>Delete</th>
            </tr>
            {% for file in epub_files %}
            <tr>
                <td>{{ file }}</td>
                <td><a href="{{ url_for('download_file', filename=file) }}"><button>Download</button></a></td>
                <td><a href="{{ url_for('delete_file', filename=file) }}"><button>Delete</button></a></td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """, epub_files=epub_files)

@app.route("/epub/download/<filename>")
def download_file(filename):
    """Serves an EPUB file for download."""
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route("/epub/delete/<filename>")
def delete_file(filename):
    """Deletes the selected EPUB file."""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for("index_epub"))



# ------------------------------
# Existing Bookmark Manager Code (unchanged)
# ------------------------------
BOOKMARK_FILE = "/home/debian/bookmark_bot/bookmarks.txt"

def read_bookmarks():
    try:
        with open(BOOKMARK_FILE, "r") as file:
            bookmarks = []
            for line in file.readlines():
                url, date_added, too_large = line.strip().split(',')
                bookmarks.append({
                    "url": url,
                    "date_added": date_added,
                    "too_large": too_large.strip().lower() == "true"
                })
            return bookmarks
    except FileNotFoundError:
        return []
    except ValueError as e:
        print(f"Error parsing bookmarks.txt: {e}")
        return []

def write_bookmarks(bookmarks):
    with open(BOOKMARK_FILE, "w") as file:
        for bookmark in bookmarks:
            file.write(f"{bookmark['url']},{bookmark['date_added']},{str(bookmark['too_large']).lower()}\n")

# Bookmark Manager HTML Template (unchanged except for the added link to the PDF manager)
bookmark_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bookmark Manager</title>
    <style>
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        tr:nth-child(odd) { background-color: #ffffff; }
        .too-large { background-color: red !important; color: white; }
    </style>
</head>
<body>
    <h1>Bookmark Manager</h1>
    
    <h2>Add a Bookmark</h2>
    <form action="/add" method="post">
        <input type="text" name="url" placeholder="Enter URL" required>
        <button type="submit">Add</button>
    </form>
    
    <h2>Remove a Bookmark</h2>
    <form action="/remove" method="post">
        <input type="text" name="url" placeholder="Enter URL" required>
        <button type="submit">Remove</button>
    </form>

    <h2>Bookmarks</h2>
    <table>
        <thead>
            <tr>
                <th>URL</th>
                <th>Date Added</th>
                <th>Too Large</th>
            </tr>
        </thead>
        <tbody>
            {% for bookmark in bookmarks %}
            <tr class="{% if bookmark.too_large %}too-large{% endif %}">
                <td>{{ bookmark.url }}</td>
                <td>{{ bookmark.date_added | datetimeformat }}</td>
                <td>{{ 'true' if bookmark.too_large else 'false' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    {% if message %}
        <p><strong>{{ message }}</strong></p>
    {% endif %}
    
    <p><a href="/pdf">Manage PDFs</a></p>
</body>
</html>
"""

@app.template_filter('datetimeformat')
def datetimeformat(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
    except ValueError:
        return value

@app.route("/", methods=["GET"])
def index():
    bookmarks = read_bookmarks()
    return render_template_string(bookmark_template, bookmarks=bookmarks, message=None)

@app.route("/add", methods=["POST"])
def add_bookmark():
    url = request.form.get("url").strip()
    if not url:
        message = "Invalid URL! Cannot add empty or whitespace-only entries."
    else:
        bookmarks = read_bookmarks()
        if any(bookmark["url"] == url for bookmark in bookmarks):
            message = "This URL is already in your bookmarks!"
        else:
            date_added = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bookmarks.append({"url": url, "date_added": date_added, "too_large": False})
            write_bookmarks(bookmarks)
            message = "Bookmark added successfully!"
    return render_template_string(bookmark_template, bookmarks=read_bookmarks(), message=message)

@app.route("/remove", methods=["POST"])
def remove_bookmark():
    url = request.form.get("url").strip()
    bookmarks = read_bookmarks()
    for bookmark in bookmarks:
        if bookmark["url"] == url:
            bookmarks.remove(bookmark)
            write_bookmarks(bookmarks)
            message = "Removed from bookmarks."
            break
    else:
        message = "This was not in your bookmarks!"
    return render_template_string(bookmark_template, bookmarks=bookmarks, message=message)

# ------------------------------
# PDF Manager Code
# ------------------------------

# File and folder settings for PDFs
PDF_LIST_FILE = "/home/debian/bookmark_bot/pdfs.txt"
PDF_UPLOAD_FOLDER = "/home/debian/bookmark_bot/pdf_uploads"

# Ensure the upload folder exists
if not os.path.exists(PDF_UPLOAD_FOLDER):
    os.makedirs(PDF_UPLOAD_FOLDER)

def read_pdf_entries():
    """Reads PDF entries from pdfs.txt. Each line is expected to be: full_file_path,date_uploaded"""
    entries = []
    if os.path.exists(PDF_LIST_FILE):
        with open(PDF_LIST_FILE, "r") as f:
            for line in f.readlines():
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    entries.append({
                        "path": parts[0],
                        "date_uploaded": parts[1]
                    })
    return entries

def append_pdf_entry(full_path, date_uploaded):
    """Appends a new PDF entry to pdfs.txt."""
    with open(PDF_LIST_FILE, "a") as f:
        f.write(f"{full_path},{date_uploaded}\n")

def remove_pdf_entry(full_path):
    """Removes an entry from pdfs.txt matching the given full file path."""
    entries = read_pdf_entries()
    entries = [entry for entry in entries if entry["path"] != full_path]
    with open(PDF_LIST_FILE, "w") as f:
        for entry in entries:
            f.write(f"{entry['path']},{entry['date_uploaded']}\n")

# HTML Template for PDF Management
pdf_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PDF Manager</title>
  <style>
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    tr:nth-child(odd) { background-color: #ffffff; }
  </style>
</head>
<body>
  <h1>PDF Manager</h1>
  
  <h2>Upload a PDF</h2>
  <form action="/pdf/upload" method="post" enctype="multipart/form-data">
      <input type="file" name="pdf_file" accept=".pdf" required>
      <button type="submit">Upload</button>
  </form>
  
  <h2>Uploaded PDFs</h2>
  <table>
    <thead>
      <tr>
        <th>Filename</th>
        <th>Date Uploaded</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody>
      {% for pdf in pdfs %}
      <tr>
        <td><a href="{{ url_for('view_pdf', filename=pdf.filename) }}">{{ pdf.filename }}</a></td>
        <td>{{ pdf.date_uploaded }}</td>
        <td>
          <!-- Summarise Button -->
          <form action="/pdf/summarise" method="post" style="display:inline;">
            <input type="hidden" name="full_path" value="{{ pdf.full_path }}">
            <button type="submit">Summarise</button>
          </form>
          <!-- Remove Button -->
          <form action="/pdf/remove" method="post" style="display:inline;">
            <input type="hidden" name="full_path" value="{{ pdf.full_path }}">
            <button type="submit">Remove</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  
  {% if message %}
    <p><strong>{{ message }}</strong></p>
  {% endif %}
  
  <p><a href="/">Back to Bookmark Manager</a></p>
</body>
</html>
"""

@app.route("/pdf", methods=["GET"])
def pdf_manager():
    entries = read_pdf_entries()
    pdfs = []
    for entry in entries:
        filename = os.path.basename(entry["path"])
        pdfs.append({
            "filename": filename,
            "full_path": entry["path"],
            "date_uploaded": entry["date_uploaded"]
        })
    return render_template_string(pdf_template, pdfs=pdfs, message=None)

@app.route("/pdf/upload", methods=["POST"])
def pdf_upload():
    if "pdf_file" not in request.files:
        return redirect(url_for("pdf_manager"))
    file = request.files["pdf_file"]
    if file.filename == "":
        return redirect(url_for("pdf_manager"))
    if file and file.filename.lower().endswith(".pdf"):
        save_path = os.path.join(PDF_UPLOAD_FOLDER, file.filename)
        file.save(save_path)
        date_uploaded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_path = os.path.abspath(save_path)
        append_pdf_entry(full_path, date_uploaded)
        message = f"Successfully uploaded {file.filename}."
    else:
        message = "Uploaded file is not a PDF."
    # Re-read entries for display.
    entries = read_pdf_entries()
    pdfs = [{"filename": os.path.basename(entry["path"]),
             "full_path": entry["path"],
             "date_uploaded": entry["date_uploaded"]} for entry in entries]
    return render_template_string(pdf_template, pdfs=pdfs, message=message)

@app.route("/pdf/view/<filename>", methods=["GET"])
def view_pdf(filename):
    return send_from_directory(PDF_UPLOAD_FOLDER, filename)

@app.route("/pdf/remove", methods=["POST"])
def pdf_remove():
    full_path = request.form.get("full_path")
    if full_path and os.path.exists(full_path):
        try:
            os.remove(full_path)
            remove_pdf_entry(full_path)
            message = "PDF removed successfully."
        except Exception as e:
            message = f"Error removing PDF: {e}"
    else:
        message = "PDF file not found."
    entries = read_pdf_entries()
    pdfs = [{"filename": os.path.basename(entry["path"]),
             "full_path": entry["path"],
             "date_uploaded": entry["date_uploaded"]} for entry in entries]
    return render_template_string(pdf_template, pdfs=pdfs, message=message)

# New Summarise Route: Calls pdf_summary.py for a given PDF
@app.route("/pdf/summarise", methods=["POST"])
def pdf_summarise():
    full_path = request.form.get("full_path")
    if not full_path or not os.path.exists(full_path):
        message = "PDF file not found."
    else:
        try:
            log_file = "/home/debian/bookmark_bot/pdf_summary.log"
            with open(log_file, "w") as log:
                process = subprocess.Popen(
                    ["python3", "/home/debian/bookmark_bot/pdf_summary.py", full_path],
                    stdout=log,
                    stderr=log,
                    env={**os.environ},  # Pass environment variables
                    cwd="/home/debian/bookmark_bot",  # Set working directory
                    start_new_session=True
                )
            message = f"Summary job triggered for: {os.path.basename(full_path)}."
        except Exception as e:
            message = f"Error triggering summary job: {e}"

    entries = read_pdf_entries()
    pdfs = [{
        "filename": os.path.basename(entry["path"]),
        "full_path": entry["path"],
        "date_uploaded": entry["date_uploaded"]
    } for entry in entries]
    return render_template_string(pdf_template, pdfs=pdfs, message=message)

# ------------------------------
# Run the Flask App
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
