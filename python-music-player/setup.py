from setuptools import setup, find_packages
import os
import sys

# Include additional data files
def get_data_files():
    # Assets directory
    data_files = []
    
    # Add icon files
    icons_dir = os.path.join('assets', 'icons')
    icons = [os.path.join(icons_dir, f) for f in os.listdir(icons_dir) if os.path.isfile(os.path.join(icons_dir, f))]
    data_files.append(('assets/icons', icons))
    
    # Add style files
    style_files = [os.path.join('assets', f) for f in os.listdir('assets') if f.endswith('.qss')]
    if style_files:
        data_files.append(('assets', style_files))
    
    # Add external binaries (ffmpeg, etc.)
    if os.path.exists('bin'):
        bin_files = [os.path.join('bin', f) for f in os.listdir('bin') if os.path.isfile(os.path.join('bin', f))]
        if bin_files:
            data_files.append(('bin', bin_files))
    
    return data_files

# Main setup configuration
setup(
    name="YTune",
    version="1.0.0",
    author="YTune Team",
    author_email="olerblaine@gmail.com",
    description="A modern music player built with Python and PySide6",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Bowling220/ytune",
    packages=find_packages(),
    include_package_data=True,
    data_files=get_data_files(),
    install_requires=[
        "PySide6>=6.4.0",
        "mutagen>=1.45.0",  # For audio metadata
        "pillow>=9.0.0",    # For image processing
        "yt-dlp>=2022.1.21",  # For YouTube downloads
        "requests>=2.27.0",
    ],
    entry_points={
        "console_scripts": [
            "ytune=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio :: Players",
    ],
    python_requires=">=3.8",
) 