#!/usr/bin/env python3
"""
Script to prepare the YTune repository for GitHub.
This script:
1. Creates a .gitignore file
2. Creates directories if they don't exist
3. Makes sure installer directory exists
"""
import os
import shutil

def main():
    print("Preparing YTune repository for GitHub...")
    
    # Create .gitignore file
    gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Distribution / packaging
.env
env/
venv/
ENV/
env.bak/
venv.bak/
.venv
.venv/

# PyInstaller
dist/
build/

# SQLite database files
*.db
*.sqlite
*.sqlite3

# Local development settings
.env
.vscode/
.idea/

# OS specific files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
"""
    
    with open(".gitignore", "w") as f:
        f.write(gitignore_content.strip())
    
    print("Created .gitignore file")
    
    # Create necessary directories if they don't exist
    dirs_to_create = [
        "installer",
        "assets/icons",
        "bin"
    ]
    
    for directory in dirs_to_create:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"Created directory: {directory}")
    
    # Make sure all necessary files exist
    if not os.path.exists("README.md"):
        print("WARNING: README.md does not exist!")
    
    if not os.path.exists("LICENSE"):
        print("WARNING: LICENSE file does not exist!")
    
    print("\nRepository is now ready for GitHub!")
    print("Next steps:")
    print("1. Initialize a Git repository: git init")
    print("2. Add all files: git add .")
    print("3. Make initial commit: git commit -m \"Initial commit\"")
    print("4. Create a new repository on GitHub")
    print("5. Add the remote: git remote add origin https://github.com/yourusername/ytune.git")
    print("6. Push to GitHub: git push -u origin master")

if __name__ == "__main__":
    main() 