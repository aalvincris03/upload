from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, send_file
import os
from werkzeug.utils import secure_filename
import requests
import base64
import json
from datetime import datetime
from PIL import Image
import io

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'py','txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', 'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}

# GitHub Configuration - Update these with your details
GITHUB_REPO = 'aalvincris03/upload'  # e.g., 'johnsmith/my-files'
GITHUB_TOKEN = ''  # Get from https://github.com/settings/tokens
GITHUB_BRANCH = 'main'  # or 'master'

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Metadata file for tracking upload timestamps
METADATA_FILE = os.path.join(UPLOAD_FOLDER, 'metadata.json')

def load_metadata():
    """Load upload metadata from JSON file"""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r') as f:
                data = json.load(f)
                # Convert upload_time strings back to datetime objects
                for filename, metadata in data.items():
                    if 'upload_time' in metadata and metadata['upload_time']:
                        try:
                            metadata['upload_time'] = datetime.fromisoformat(metadata['upload_time'])
                        except (ValueError, TypeError):
                            metadata['upload_time'] = None
                return data
        except:
            return {}
    return {}

def save_metadata(metadata):
    """Save upload metadata to JSON file"""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_github(file_path, filename):
    """Upload file to GitHub repository using GitHub API"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        return False  # Skip if not configured

    try:
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Encode to base64
        encoded_content = base64.b64encode(file_content).decode('utf-8')

        # GitHub API URL
        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads/{filename}'

        # Headers
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # Check if file already exists
        response = requests.get(url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json()['sha']

        # Prepare data for upload
        data = {
            'message': f'Upload file: {filename}',
            'content': encoded_content,
            'branch': GITHUB_BRANCH
        }
        if sha:
            data['sha'] = sha

        # Upload file
        response = requests.put(url, headers=headers, json=data)

        return response.status_code in [200, 201]

    except Exception as e:
        print(f"GitHub upload error: {e}")
        return False

def delete_from_github(filename):
    """Delete file from GitHub repository using GitHub API"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        return False  # Skip if not configured

    try:
        # GitHub API URL
        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads/{filename}'

        # Headers
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # Get file SHA
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return False  # File doesn't exist on GitHub

        sha = response.json()['sha']

        # Prepare data for deletion
        data = {
            'message': f'Delete file: {filename}',
            'sha': sha,
            'branch': GITHUB_BRANCH
        }

        # Delete file
        response = requests.delete(url, headers=headers, json=data)

        return response.status_code == 200

    except Exception as e:
        print(f"GitHub delete error: {e}")
        return False

def get_github_files():
    """Get list of files from GitHub repository"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        return []

    try:
        # GitHub API URL for uploads folder
        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads'

        # Headers
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # Get list of files from GitHub
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch GitHub files: {response.status_code}")
            return []

        github_files = response.json()
        if not isinstance(github_files, list):
            print("Unexpected GitHub response format")
            return []

        # Extract file names
        files = []
        for item in github_files:
            if item['type'] == 'file':
                files.append(item['name'])

        return files

    except Exception as e:
        print(f"GitHub files fetch error: {e}")
        return []

def sync_from_github():
    """Sync files from GitHub repository to local folder"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        return False, "GitHub not configured"

    try:
        # GitHub API URL for uploads folder
        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads'

        # Headers
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # Get list of files from GitHub
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return False, f"Failed to fetch GitHub files: {response.status_code}"

        github_files = response.json()
        if not isinstance(github_files, list):
            return False, "Unexpected GitHub response format"

        # Get local files
        local_files = set(os.listdir(UPLOAD_FOLDER))

        synced_count = 0
        for item in github_files:
            if item['type'] == 'file':
                filename = item['name']
                if filename not in local_files:
                    # Download file from GitHub
                    file_url = item['download_url']
                    file_response = requests.get(file_url)
                    if file_response.status_code == 200:
                        file_path = os.path.join(UPLOAD_FOLDER, filename)
                        with open(file_path, 'wb') as f:
                            f.write(file_response.content)

                        # Record sync timestamp
                        metadata = load_metadata()
                        metadata[filename] = {
                            'upload_time': datetime.now(),
                            'size': os.path.getsize(file_path)
                        }
                        save_metadata(metadata)

                        synced_count += 1
                        print(f"Synced file: {filename}")
                    else:
                        print(f"Failed to download {filename}: {file_response.status_code}")

        return True, f"Successfully synced {synced_count} files from GitHub"

    except Exception as e:
        print(f"GitHub sync error: {e}")
        return False, str(e)

def sync_to_github():
    """Sync local files to GitHub repository"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        return False, "GitHub not configured"

    try:
        # Get GitHub files
        github_files = get_github_files()
        github_files_set = set(github_files)

        # Get local files
        local_files = os.listdir(UPLOAD_FOLDER)

        synced_count = 0
        for filename in local_files:
            if filename not in github_files_set:
                # Upload file to GitHub
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(file_path):
                    success = upload_to_github(file_path, filename)
                    if success:
                        synced_count += 1
                        print(f"Synced file to GitHub: {filename}")
                    else:
                        print(f"Failed to sync {filename} to GitHub")

        return True, f"Successfully synced {synced_count} files to GitHub"

    except Exception as e:
        print(f"GitHub sync to error: {e}")
        return False, str(e)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/files')
def index():
    local_files = os.listdir(app.config['UPLOAD_FOLDER'])
    github_files = get_github_files()
    metadata = load_metadata()

    # Combine and deduplicate files
    all_files = list(set(local_files + github_files))

    # Create file info dictionary
    files_info = {}
    for file in all_files:
        file_info = {
            'local': file in local_files,
            'github': file in github_files,
            'upload_time': None,
            'size': None,
            'extension': file.rsplit('.', 1)[1].lower() if '.' in file else ''
        }

        # Add metadata if available
        if file in metadata:
            file_info['upload_time'] = metadata[file].get('upload_time')
            file_info['size'] = metadata[file].get('size')

        files_info[file] = file_info

    # Get sort parameter
    sort_by = request.args.get('sort', 'time_newest')

    # Sort files based on the parameter
    if sort_by == 'name_asc':
        sorted_files = sorted(files_info.items(), key=lambda x: x[0].lower())
    elif sort_by == 'name_desc':
        sorted_files = sorted(files_info.items(), key=lambda x: x[0].lower(), reverse=True)
    elif sort_by == 'time_newest':
        sorted_files = sorted(files_info.items(),
                            key=lambda x: x[1]['upload_time'] if x[1]['upload_time'] else datetime.min,
                            reverse=True)
    elif sort_by == 'time_oldest':
        sorted_files = sorted(files_info.items(),
                            key=lambda x: x[1]['upload_time'] if x[1]['upload_time'] else datetime.max)
    elif sort_by == 'size_largest':
        sorted_files = sorted(files_info.items(),
                            key=lambda x: x[1]['size'] if x[1]['size'] else 0,
                            reverse=True)
    elif sort_by == 'size_smallest':
        sorted_files = sorted(files_info.items(),
                            key=lambda x: x[1]['size'] if x[1]['size'] else float('inf'))
    elif sort_by == 'type_asc':
        sorted_files = sorted(files_info.items(), key=lambda x: x[1]['extension'])
    elif sort_by == 'type_desc':
        sorted_files = sorted(files_info.items(), key=lambda x: x[1]['extension'], reverse=True)
    else:
        sorted_files = list(files_info.items())

    # Convert back to dictionary
    sorted_files_info = dict(sorted_files)

    return render_template('index.html', files_info=sorted_files_info, current_sort=sort_by)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        # Redirect to main page if someone tries to access /upload directly
        return redirect(url_for('index'))

    # Handle POST request for file upload
    if 'files' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))

    files = request.files.getlist('files')

    if not files or all(file.filename == '' for file in files):
        flash('No selected files')
        return redirect(url_for('index'))

    uploaded_count = 0
    github_uploaded_count = 0

    for file in files:
        if file.filename == '':
            continue

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Check file size for videos (30MB max)
            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext in {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}:
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)  # Reset file pointer
                if file_size > 30 * 1024 * 1024:  # 30MB in bytes
                    flash(f'Video file "{filename}" exceeds 30MB limit')
                    continue

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Record upload timestamp
            metadata = load_metadata()
            metadata[filename] = {
                'upload_time': datetime.now(),
                'size': os.path.getsize(file_path)
            }
            save_metadata(metadata)

            uploaded_count += 1

            # Upload to GitHub
            github_success = upload_to_github(file_path, filename)
            if github_success:
                github_uploaded_count += 1

    if uploaded_count > 0:
        flash(f'Successfully uploaded {uploaded_count} file(s)')
        if github_uploaded_count > 0:
            flash(f'{github_uploaded_count} file(s) also uploaded to GitHub repository')
        elif github_uploaded_count < uploaded_count:
            flash('Files uploaded locally, but some GitHub uploads failed (check configuration)')
    else:
        flash('No valid files were uploaded')

    return redirect(url_for('index'))

def preview_github_file(filename):
    """Preview file from GitHub repository"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        return None

    try:
        # GitHub API URL for raw content
        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads/{filename}'

        # Headers for raw content with authentication
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3.raw'
        }

        # Get raw file content
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None

        # Return file content with appropriate headers
        from flask import Response
        return Response(response.content, mimetype=response.headers.get('content-type', 'application/octet-stream'))

    except Exception as e:
        print(f"GitHub preview error: {e}")
        return None

def download_github_file(filename):
    """Download file from GitHub repository"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        return None

    try:
        # GitHub API URL for raw content
        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads/{filename}'

        # Headers for raw content with authentication
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3.raw'
        }

        # Get raw file content
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None

        # Return file content with appropriate headers for download
        from flask import Response
        return Response(response.content,
                       mimetype=response.headers.get('content-type', 'application/octet-stream'),
                       headers={"Content-Disposition": f"attachment; filename={filename}"})

    except Exception as e:
        print(f"GitHub download error: {e}")
        return None

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        # Try to fetch from GitHub if not found locally
        result = download_github_file(filename)
        if result is not None:
            return result
        else:
            flash('File not found')
            return redirect(url_for('index'))

@app.route('/preview/<filename>')
def preview_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)
    except FileNotFoundError:
        # Try to fetch from GitHub if not found locally
        result = preview_github_file(filename)
        if result is not None:
            return result
        else:
            flash('File not found')
            return redirect(url_for('index'))

@app.route('/get_content/<filename>')
def get_file_content(filename):
    """Get file content for preview display"""
    text_extensions = ['.txt', '.py', '.md', '.html', '.css', '.js', '.json', '.xml', '.csv']

    if not any(filename.lower().endswith(ext) for ext in text_extensions):
        return {'error': 'Not a text file'}, 400

    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # Read first 1000 characters
                truncated = len(content) >= 1000
                return {'content': content, 'truncated': truncated}
        else:
            # Try to get from GitHub
            if GITHUB_REPO != 'your-username/your-repo-name' and GITHUB_TOKEN != 'your-github-personal-access-token':
                try:
                    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads/{filename}'
                    headers = {
                        'Authorization': f'Bearer {GITHUB_TOKEN}',
                        'Accept': 'application/vnd.github.v3.raw'
                    }
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        content = response.text[:1000]  # First 1000 characters
                        truncated = len(response.text) > 1000
                        return {'content': content, 'truncated': truncated}
                except:
                    pass

        return {'error': 'File not found'}, 404
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/delete/<filename>')
def delete_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)

        # Remove metadata
        metadata = load_metadata()
        if filename in metadata:
            del metadata[filename]
            save_metadata(metadata)

        # Delete from GitHub (only if file exists on GitHub)
        github_success = delete_from_github(filename)
        if github_success:
            flash('File successfully deleted from local and GitHub repository')
        else:
            # Check if file exists on GitHub first
            github_files = get_github_files()
            if filename in github_files:
                flash('File deleted locally, but GitHub deletion failed (check configuration)')
            else:
                flash('File successfully deleted locally (not found on GitHub)')
    else:
        flash('File not found')
    return redirect(url_for('index'))

@app.route('/sync')
def sync_files():
    """Sync files bidirectionally between local and GitHub repository"""
    # Sync from GitHub to local
    success_from, message_from = sync_from_github()

    # Sync from local to GitHub
    success_to, message_to = sync_to_github()

    if success_from and success_to:
        flash(f'{message_from}. {message_to}')
    elif success_from:
        flash(f'{message_from}. Sync to GitHub failed: {message_to}')
    elif success_to:
        flash(f'Sync from GitHub failed: {message_from}. {message_to}')
    else:
        flash(f'Sync failed: {message_from}. {message_to}')

    return redirect(url_for('index'))

@app.route('/sync_file/<filename>')
def sync_file(filename):
    """Sync a specific file from GitHub to local storage"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        flash('GitHub not configured')
        return redirect(url_for('index'))

    try:
        # GitHub API URL for file content
        url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads/{filename}'

        # Headers
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # Get file info from GitHub
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            flash(f'File "{filename}" not found on GitHub')
            return redirect(url_for('index'))

        file_info = response.json()
        download_url = file_info['download_url']

        # Download file content
        file_response = requests.get(download_url)
        if file_response.status_code != 200:
            flash(f'Failed to download file "{filename}" from GitHub')
            return redirect(url_for('index'))

        # Save file locally
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, 'wb') as f:
            f.write(file_response.content)

        # Record sync timestamp
        metadata = load_metadata()
        metadata[filename] = {
            'upload_time': datetime.now(),
            'size': os.path.getsize(file_path)
        }
        save_metadata(metadata)

        flash(f'File "{filename}" successfully synced from GitHub to local storage')
        return redirect(url_for('index'))

    except Exception as e:
        print(f"File sync error: {e}")
        flash(f'Failed to sync file "{filename}": {str(e)}')
        return redirect(url_for('index'))

@app.route('/sync_to_github/<filename>')
def sync_to_github_file(filename):
    """Sync a specific file from local storage to GitHub repository"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        flash('GitHub not configured')
        return redirect(url_for('index'))

    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        flash(f'File "{filename}" not found locally')
        return redirect(url_for('index'))

    success = upload_to_github(file_path, filename)
    if success:
        flash(f'File "{filename}" successfully synced to GitHub repository')
    else:
        flash(f'Failed to sync file "{filename}" to GitHub repository')

    return redirect(url_for('index'))

@app.route('/sync_to_github')
def sync_to_github_route():
    """Sync local files to GitHub repository"""
    success, message = sync_to_github()
    if success:
        flash(message)
    else:
        flash(f'Sync to GitHub failed: {message}')
    return redirect(url_for('index'))

@app.route('/delete_local/<filename>')
def delete_local(filename):
    """Delete file from local storage only"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)

        # Remove metadata
        metadata = load_metadata()
        if filename in metadata:
            del metadata[filename]
            save_metadata(metadata)

        flash(f'File "{filename}" successfully deleted from local storage')
    else:
        flash('File not found locally')
    return redirect(url_for('index'))

@app.route('/delete_github/<filename>')
def delete_github(filename):
    """Delete file from GitHub repository only"""
    github_success = delete_from_github(filename)
    if github_success:
        flash(f'File "{filename}" successfully deleted from GitHub repository')
    else:
        flash('File not found on GitHub or deletion failed')
    return redirect(url_for('index'))

@app.route('/delete_both/<filename>')
def delete_both(filename):
    """Delete file from both local storage and GitHub repository"""
    # Delete from local
    local_deleted = False
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        local_deleted = True

        # Remove metadata
        metadata = load_metadata()
        if filename in metadata:
            del metadata[filename]
            save_metadata(metadata)

    # Delete from GitHub
    github_success = delete_from_github(filename)

    if local_deleted and github_success:
        flash(f'File "{filename}" successfully deleted from both local storage and GitHub repository')
    elif local_deleted:
        flash(f'File "{filename}" deleted locally, but GitHub deletion failed')
    elif github_success:
        flash(f'File "{filename}" deleted from GitHub, but not found locally')
    else:
        flash('File not found in either location')

    return redirect(url_for('index'))

@app.route('/create_file', methods=['POST'])
def create_file():
    """Create a new file with provided content and upload it"""
    filename = request.form.get('filename', '').strip()
    extension = request.form.get('extension', '.txt')
    content = request.form.get('content', '')

    if not filename:
        flash('Filename is required')
        return redirect(url_for('index'))

    # Combine filename and extension
    full_filename = secure_filename(filename + extension)

    # Validate extension
    if extension not in ['.txt', '.py']:
        flash('Invalid file extension. Only .txt and .py are allowed.')
        return redirect(url_for('index'))

    # Check if file already exists
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], full_filename)
    if os.path.exists(file_path):
        flash(f'File "{full_filename}" already exists')
        return redirect(url_for('index'))

    try:
        # Create the file with content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Record upload timestamp
        metadata = load_metadata()
        metadata[full_filename] = {
            'upload_time': datetime.now(),
            'size': os.path.getsize(file_path)
        }
        save_metadata(metadata)

        # Upload to GitHub
        github_success = upload_to_github(file_path, full_filename)

        if github_success:
            flash(f'File "{full_filename}" created and uploaded successfully')
        else:
            flash(f'File "{full_filename}" created locally, but GitHub upload failed (check configuration)')

    except Exception as e:
        flash(f'Error creating file: {str(e)}')

    return redirect(url_for('index'))

@app.route('/edit_file/<filename>', methods=['POST'])
def edit_file(filename):
    """Edit an existing file with new content and upload it"""
    new_filename = request.form.get('filename', '').strip()
    extension = request.form.get('extension', '.txt')
    content = request.form.get('content', '')

    if not new_filename:
        flash('Filename is required')
        return redirect(url_for('index'))

    # Combine new filename and extension
    new_full_filename = secure_filename(new_filename + extension)

    # Validate extension
    if extension not in ['.txt', '.py']:
        flash('Invalid file extension. Only .txt and .py are allowed.')
        return redirect(url_for('index'))

    # Check if the new filename already exists (if different from original)
    if new_full_filename != filename:
        new_file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_full_filename)
        if os.path.exists(new_file_path):
            flash(f'File "{new_full_filename}" already exists')
            return redirect(url_for('index'))

    try:
        # Check if original file exists
        original_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(original_file_path):
            flash(f'Original file "{filename}" not found')
            return redirect(url_for('index'))

        # If filename changed, delete the old file from GitHub first
        if new_full_filename != filename:
            delete_from_github(filename)

        # Update the file with new content
        new_file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_full_filename)
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # If filename changed, remove old file and metadata
        if new_full_filename != filename:
            os.remove(original_file_path)
            metadata = load_metadata()
            if filename in metadata:
                del metadata[filename]
            metadata[new_full_filename] = {
                'upload_time': datetime.now(),
                'size': os.path.getsize(new_file_path)
            }
            save_metadata(metadata)
        else:
            # Update metadata for existing file
            metadata = load_metadata()
            metadata[new_full_filename] = {
                'upload_time': datetime.now(),
                'size': os.path.getsize(new_file_path)
            }
            save_metadata(metadata)

        # Upload to GitHub
        github_success = upload_to_github(new_file_path, new_full_filename)

        if github_success:
            flash(f'File "{new_full_filename}" updated and uploaded successfully')
        else:
            flash(f'File "{new_full_filename}" updated locally, but GitHub upload failed (check configuration)')

    except Exception as e:
        flash(f'Error updating file: {str(e)}')

    return redirect(url_for('index'))

@app.route('/delete_all')
def delete_all_files():
    """Delete all files based on target parameter"""
    target = request.args.get('target', 'both')  # Default to 'both' for backward compatibility

    if target not in ['local', 'github', 'both']:
        flash('Invalid target parameter. Use local, github, or both.')
        return redirect(url_for('index'))

    deleted_local_count = 0
    deleted_github_count = 0

    if target in ['local', 'both']:
        # Delete all local files
        local_files = os.listdir(app.config['UPLOAD_FOLDER'])
        for filename in local_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_local_count += 1

        # Clear metadata file
        if os.path.exists(METADATA_FILE):
            os.remove(METADATA_FILE)

    if target in ['github', 'both']:
        # Delete all GitHub files
        github_files = get_github_files()
        for filename in github_files:
            github_success = delete_from_github(filename)
            if github_success:
                deleted_github_count += 1
            else:
                print(f"Failed to delete {filename} from GitHub")

    # Generate appropriate message
    if target == 'local':
        if deleted_local_count > 0:
            flash(f'Successfully deleted {deleted_local_count} files from local storage')
        else:
            flash('No local files to delete')
    elif target == 'github':
        if deleted_github_count > 0:
            flash(f'Successfully deleted {deleted_github_count} files from GitHub repository')
        else:
            flash('No GitHub files to delete')
    else:  # both
        local_msg = f'{deleted_local_count} from local storage' if deleted_local_count > 0 else 'no local files'
        github_msg = f'{deleted_github_count} from GitHub repository' if deleted_github_count > 0 else 'no GitHub files'
        flash(f'Successfully deleted {local_msg} and {github_msg}')

    return redirect(url_for('index'))

@app.route('/convert')
def convert():
    local_files = os.listdir(app.config['UPLOAD_FOLDER'])
    github_files = get_github_files()
    metadata = load_metadata()

    # Combine and deduplicate files
    all_files = list(set(local_files + github_files))

    # Create file info dictionary
    files_info = {}
    for file in all_files:
        file_info = {
            'local': file in local_files,
            'github': file in github_files,
            'upload_time': None,
            'size': None,
            'extension': file.rsplit('.', 1)[1].lower() if '.' in file else ''
        }

        # Add metadata if available
        if file in metadata:
            file_info['upload_time'] = metadata[file].get('upload_time')
            file_info['size'] = metadata[file].get('size')

        files_info[file] = file_info

    return render_template('convert.html', files_info=files_info)

@app.route('/convert_image', methods=['POST'])
def convert_image():
    """Convert uploaded images to specified format"""
    if 'images' not in request.files:
        flash('No image files provided')
        return redirect(url_for('convert'))

    files = request.files.getlist('images')
    to_format = request.form.get('to_format', '').lower()

    if not files or all(file.filename == '' for file in files):
        flash('No image files selected')
        return redirect(url_for('convert'))

    if not to_format:
        flash('Please specify target format')
        return redirect(url_for('convert'))

    # Validate target format
    supported_formats = ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp', 'gif']
    if to_format not in supported_formats:
        flash('Unsupported target format')
        return redirect(url_for('convert'))

    # Create converted folder if it doesn't exist
    converted_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'converted')
    os.makedirs(converted_folder, exist_ok=True)

    converted_images = []
    converted_count = 0

    for file in files:
        if file.filename == '':
            continue

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            try:
                # Open image with PIL to detect format
                image = Image.open(file)

                # Detect source format from PIL
                detected_format = image.format.lower() if image.format else None

                # If PIL can't detect format, try from filename extension
                if not detected_format:
                    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    if file_ext in supported_formats:
                        detected_format = file_ext

                # Skip if format not supported
                if not detected_format or detected_format not in supported_formats:
                    continue

                # Skip if source and target formats are the same
                if detected_format == to_format:
                    continue

                # Convert to RGB if necessary (for JPEG)
                if to_format in ['jpg', 'jpeg'] and image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')

                # Generate new filename
                name_without_ext = filename.rsplit('.', 1)[0]
                new_filename = f"{name_without_ext}_converted.{to_format}"
                converted_path = os.path.join(converted_folder, new_filename)

                # Save converted image
                if to_format in ['jpg', 'jpeg']:
                    image.save(converted_path, 'JPEG', quality=95)
                elif to_format == 'png':
                    image.save(converted_path, 'PNG')
                elif to_format == 'bmp':
                    image.save(converted_path, 'BMP')
                elif to_format == 'tiff':
                    image.save(converted_path, 'TIFF')
                elif to_format == 'webp':
                    image.save(converted_path, 'WEBP')
                elif to_format == 'gif':
                    image.save(converted_path, 'GIF')

                converted_images.append({
                    'filename': new_filename,
                    'original_name': filename,
                    'conversion': f"{detected_format.upper()} → {to_format.upper()}",
                    'format_badge': to_format.upper()
                })

                converted_count += 1

            except Exception as e:
                print(f"Error converting {filename}: {e}")
                continue

    if converted_count > 0:
        flash(f'Successfully converted {converted_count} image(s)')
        # Get files_info for the template
        local_files = os.listdir(app.config['UPLOAD_FOLDER'])
        github_files = get_github_files()
        metadata = load_metadata()

        # Combine and deduplicate files
        all_files = list(set(local_files + github_files))

        # Create file info dictionary
        files_info = {}
        for file in all_files:
            file_info = {
                'local': file in local_files,
                'github': file in github_files,
                'upload_time': None,
                'size': None,
                'extension': file.rsplit('.', 1)[1].lower() if '.' in file else ''
            }

            # Add metadata if available
            if file in metadata:
                file_info['upload_time'] = metadata[file].get('upload_time')
                file_info['size'] = metadata[file].get('size')

            files_info[file] = file_info

        return render_template('convert.html', converted_images=converted_images, files_info=files_info)
    else:
        flash('No images were successfully converted')
        return redirect(url_for('convert'))

@app.route('/download_converted/<filename>')
def download_converted(filename):
    """Download converted image"""
    converted_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'converted')
    try:
        return send_from_directory(converted_folder, filename, as_attachment=True)
    except FileNotFoundError:
        flash('Converted file not found')
        return redirect(url_for('convert'))

@app.route('/upload_converted/<filename>')
def upload_converted(filename):
    """Upload converted image to GitHub repository"""
    if GITHUB_REPO == 'your-username/your-repo-name' or GITHUB_TOKEN == 'your-github-personal-access-token':
        flash('GitHub not configured')
        return redirect(url_for('convert'))

    converted_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'converted')
    file_path = os.path.join(converted_folder, filename)

    if not os.path.exists(file_path):
        flash(f'Converted file "{filename}" not found')
        return redirect(url_for('convert'))

    success = upload_to_github(file_path, filename)
    if success:
        flash(f'Converted file "{filename}" successfully uploaded to GitHub repository')
    else:
        flash(f'Failed to upload converted file "{filename}" to GitHub repository')

    return redirect(url_for('convert'))

@app.route('/convert_selected_images', methods=['POST'])
def convert_selected_images():
    """Convert selected uploaded images to specified format"""
    selected_images = request.form.getlist('selected_images')
    to_format = request.form.get('to_format', '').lower()

    if not selected_images:
        flash('No images selected')
        return redirect(url_for('convert'))

    if not to_format:
        flash('Please specify target format')
        return redirect(url_for('convert'))

    # Validate target format
    supported_formats = ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp', 'gif']
    if to_format not in supported_formats:
        flash('Unsupported target format')
        return redirect(url_for('convert'))

    # Create converted folder if it doesn't exist
    converted_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'converted')
    os.makedirs(converted_folder, exist_ok=True)

    converted_images = []
    converted_count = 0

    for filename in selected_images:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Check if file exists locally
        if not os.path.exists(file_path):
            # Try to sync from GitHub if not found locally
            if GITHUB_REPO != 'your-username/your-repo-name' and GITHUB_TOKEN != 'your-github-personal-access-token':
                try:
                    # GitHub API URL for file content
                    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/uploads/{filename}'

                    # Headers
                    headers = {
                        'Authorization': f'Bearer {GITHUB_TOKEN}',
                        'Accept': 'application/vnd.github.v3+json'
                    }

                    # Get file info from GitHub
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        file_info = response.json()
                        download_url = file_info['download_url']

                        # Download file content
                        file_response = requests.get(download_url)
                        if file_response.status_code == 200:
                            with open(file_path, 'wb') as f:
                                f.write(file_response.content)

                            # Record sync timestamp
                            metadata = load_metadata()
                            metadata[filename] = {
                                'upload_time': datetime.now(),
                                'size': os.path.getsize(file_path)
                            }
                            save_metadata(metadata)
                        else:
                            continue  # Skip if download failed
                    else:
                        continue  # Skip if not found on GitHub
                except:
                    continue  # Skip if sync failed
            else:
                continue  # Skip if not found locally and GitHub not configured

        try:
            # Open image with PIL to detect format
            with open(file_path, 'rb') as f:
                image = Image.open(f)

                # Detect source format from PIL
                detected_format = image.format.lower() if image.format else None

                # If PIL can't detect format, try from filename extension
                if not detected_format:
                    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    if file_ext in supported_formats:
                        detected_format = file_ext

                # Skip if format not supported
                if not detected_format or detected_format not in supported_formats:
                    continue

                # Skip if source and target formats are the same
                if detected_format == to_format:
                    continue

                # Convert to RGB if necessary (for JPEG)
                if to_format in ['jpg', 'jpeg'] and image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')

                # Generate new filename
                name_without_ext = filename.rsplit('.', 1)[0]
                new_filename = f"{name_without_ext}_converted.{to_format}"
                converted_path = os.path.join(converted_folder, new_filename)

                # Save converted image
                if to_format in ['jpg', 'jpeg']:
                    image.save(converted_path, 'JPEG', quality=95)
                elif to_format == 'png':
                    image.save(converted_path, 'PNG')
                elif to_format == 'bmp':
                    image.save(converted_path, 'BMP')
                elif to_format == 'tiff':
                    image.save(converted_path, 'TIFF')
                elif to_format == 'webp':
                    image.save(converted_path, 'WEBP')
                elif to_format == 'gif':
                    image.save(converted_path, 'GIF')

                converted_images.append({
                    'filename': new_filename,
                    'original_name': filename,
                    'conversion': f"{detected_format.upper()} → {to_format.upper()}",
                    'format_badge': to_format.upper()
                })

                converted_count += 1

        except Exception as e:
            print(f"Error converting {filename}: {e}")
            continue

    if converted_count > 0:
        flash(f'Successfully converted {converted_count} image(s)')
        # Get files_info for the template
        local_files = os.listdir(app.config['UPLOAD_FOLDER'])
        github_files = get_github_files()
        metadata = load_metadata()

        # Combine and deduplicate files
        all_files = list(set(local_files + github_files))

        # Create file info dictionary
        files_info = {}
        for file in all_files:
            file_info = {
                'local': file in local_files,
                'github': file in github_files,
                'upload_time': None,
                'size': None,
                'extension': file.rsplit('.', 1)[1].lower() if '.' in file else ''
            }

            # Add metadata if available
            if file in metadata:
                file_info['upload_time'] = metadata[file].get('upload_time')
                file_info['size'] = metadata[file].get('size')

            files_info[file] = file_info

        return render_template('convert.html', converted_images=converted_images, files_info=files_info)
    else:
        flash('No images were successfully converted')
        return redirect(url_for('convert'))

if __name__ == '__main__':
    app.run(debug=True)
