from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import os
from werkzeug.utils import secure_filename
import requests
import base64

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'py','txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', 'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}

# GitHub Configuration - Update these with your details
GITHUB_REPO = 'aalvincris03/upload'  # e.g., 'johnsmith/my-files'
GITHUB_TOKEN = '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'  # Get from https://github.com/settings/tokens
GITHUB_BRANCH = 'main'  # or 'master'

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
            'Authorization': f'token {GITHUB_TOKEN}',
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
            'Authorization': f'token {GITHUB_TOKEN}',
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
            'Authorization': f'token {GITHUB_TOKEN}',
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
            'Authorization': f'token {GITHUB_TOKEN}',
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
                        synced_count += 1
                        print(f"Synced file: {filename}")
                    else:
                        print(f"Failed to download {filename}: {file_response.status_code}")

        return True, f"Successfully synced {synced_count} files from GitHub"

    except Exception as e:
        print(f"GitHub sync error: {e}")
        return False, str(e)

@app.route('/')
def index():
    local_files = os.listdir(app.config['UPLOAD_FOLDER'])
    github_files = get_github_files()

    # Combine and deduplicate files
    all_files = list(set(local_files + github_files))

    # Create file info dictionary
    files_info = {}
    for file in all_files:
        files_info[file] = {
            'local': file in local_files,
            'github': file in github_files
        }

    return render_template('index.html', files_info=files_info)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        # Check file size for videos (30MB max)
        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext in {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'}:
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset file pointer
            if file_size > 30 * 1024 * 1024:  # 30MB in bytes
                flash('Video file size exceeds 30MB limit')
                return redirect(request.url)

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        flash('File successfully uploaded')

        # Upload to GitHub
        github_success = upload_to_github(file_path, filename)
        if github_success:
            flash('File also uploaded to GitHub repository')
        else:
            flash('File uploaded locally, but GitHub upload failed (check configuration)')

        return redirect(url_for('index'))
    else:
        flash('Allowed file types are: ' + ', '.join(ALLOWED_EXTENSIONS))
        return redirect(request.url)

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found')
        return redirect(url_for('index'))

@app.route('/delete/<filename>')
def delete_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)

        # Delete from GitHub
        github_success = delete_from_github(filename)
        if github_success:
            flash('File successfully deleted from local and GitHub repository')
        else:
            flash('File deleted locally, but GitHub deletion failed (check configuration)')
    else:
        flash('File not found')
    return redirect(url_for('index'))

@app.route('/sync')
def sync_files():
    """Sync files from GitHub repository to local folder"""
    success, message = sync_from_github()
    if success:
        flash(message)
    else:
        flash(f'Sync failed: {message}')
    return redirect(url_for('index'))

@app.route('/delete_all')
def delete_all_files():
    """Delete all local files and corresponding GitHub files"""
    local_files = os.listdir(app.config['UPLOAD_FOLDER'])
    deleted_count = 0

    for filename in local_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)

            # Delete from GitHub
            github_success = delete_from_github(filename)
            if github_success:
                deleted_count += 1
            else:
                print(f"Failed to delete {filename} from GitHub")

    if deleted_count > 0:
        flash(f'Successfully deleted {deleted_count} files from local storage and GitHub repository')
    else:
        flash('No files to delete')

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
