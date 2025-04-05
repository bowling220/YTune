# core/scanner.py
import os
import time
from mutagen import File as MutagenFile, MutagenError
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4 # For m4a
from mutagen.id3 import ID3NoHeaderError

from PySide6.QtCore import QObject, Signal, QRunnable, Slot
from typing import List, Set

from .models import Track
from .database import Database

# Supported file extensions (lowercase)
SUPPORTED_EXTENSIONS = {
    '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wav', '.wma',
    '.mp4', '.mov', '.m4b', '.m4p', '.m4v'  # Add all MP4 container variants
} # Added all MP4 file formats


class ScannerSignals(QObject):
    """Signals for the media scanner worker."""
    progress = Signal(int, int)  # (processed, total)
    scan_finished = Signal(int)  # total tracks found
    error_occurred = Signal(str)  # error message
    file_found = Signal(str)            # filepath found


class MediaScanner(QRunnable):
    """Worker class to scan directories for media files."""
    
    AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.flac', '.wav', '.ogg', '.opus'}
    
    def __init__(self, directories: List[str]):
        super().__init__()
        self.directories = directories
        self.signals = ScannerSignals()
        self.should_stop = False
        
    def cancel(self):
        """Cancel the scan."""
        self.should_stop = True
        
    @Slot()
    def run(self):
        """Start scanning the directories."""
        start_time = time.time()
        try:
            # Create database connection
            db = Database()
            
            # Find all valid audio files
            all_files = self._find_audio_files()
            if self.should_stop:
                return
                
            # Process each file and add to database
            processed_count = 0
            total_count = len(all_files)
            valid_files = []
            
            self.signals.progress.emit(processed_count, total_count)
            
            for filepath in all_files:
                if self.should_stop:
                    self.signals.scan_finished.emit(processed_count)
                    return
                
                if self._process_file(filepath, db):
                    valid_files.append(filepath)
                
                processed_count += 1
                if processed_count % 10 == 0 or processed_count == total_count:
                    self.signals.progress.emit(processed_count, total_count)
            
            # Remove tracks from database that no longer exist in the filesystem
            db.remove_tracks_not_in_list(valid_files)
            
            self.signals.scan_finished.emit(processed_count)
            
            scan_time = time.time() - start_time
            print(f"Scan completed in {scan_time:.2f} seconds, found {processed_count} files")
            
        except Exception as e:
            self.signals.error_occurred.emit(f"Scan error: {str(e)}")
            self.signals.scan_finished.emit(0)
            
    def _find_audio_files(self) -> List[str]:
        """Find all audio files in the directories."""
        all_files = []
        
        for directory in self.directories:
            # Skip if directory doesn't exist
            if not os.path.isdir(directory):
                print(f"Warning: Directory not found: {directory}")
                continue
                
            # Walk through directory
            for root, _, files in os.walk(directory):
                if self.should_stop:
                    return all_files
                    
                for filename in files:
                    # Check if file has audio extension
                    _, ext = os.path.splitext(filename.lower())
                    if ext in self.AUDIO_EXTENSIONS:
                        filepath = os.path.join(root, filename)
                        all_files.append(filepath)
                        
        return all_files
        
    def _process_file(self, filepath: str, db: Database) -> bool:
        """Process a single audio file and add to database."""
        try:
            # Extract metadata
            metadata = self._extract_metadata(filepath)
            
            # Create Track object
            track = Track(
                filepath=filepath,
                title=metadata.get('title', ''),
                artist=metadata.get('artist', ''),
                album=metadata.get('album', ''),
                genre=metadata.get('genre', ''),
                length=metadata.get('length', 0),
                album_art=metadata.get('album_art')
            )
            
            # Store in database
            db.add_or_update_track(track)
            return True
        except Exception as e:
            print(f"Error processing file: {filepath}")
            print(f"Exception: {e}")
            return False
            
    def _extract_metadata(self, filepath: str) -> dict:
        """Extract metadata from an audio file."""
        metadata = {}
        
        try:
            audio = MutagenFile(filepath)
            if audio is None:
                return metadata
                
            # Get basic info like duration
            if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                metadata['length'] = audio.info.length
                
            # MP3-specific tags
            if isinstance(audio, MP3):
                # ID3 tags
                if hasattr(audio, 'tags'):
                    tags = audio.tags
                    if tags:
                        # Common ID3 fields
                        if 'TIT2' in tags:  # Title
                            metadata['title'] = str(tags['TIT2'])
                        if 'TPE1' in tags:  # Artist
                            metadata['artist'] = str(tags['TPE1'])
                        if 'TALB' in tags:  # Album
                            metadata['album'] = str(tags['TALB'])
                        if 'TCON' in tags:  # Genre
                            metadata['genre'] = str(tags['TCON'])
                        
                        # Album art
                        if 'APIC:' in tags or 'APIC' in tags:
                            apic_tag = tags.get('APIC:') or tags.get('APIC')
                            if apic_tag:
                                metadata['album_art'] = apic_tag.data
            
            # Generic (non-MP3) tags
            elif hasattr(audio, 'tags'):
                tags = audio.tags
                if tags:
                    # Try common tag names
                    for field, tag_names in {
                        'title': ['title', 'TITLE'],
                        'artist': ['artist', 'ARTIST'],
                        'album': ['album', 'ALBUM'],
                        'genre': ['genre', 'GENRE']
                    }.items():
                        for tag in tag_names:
                            if tag in tags:
                                metadata[field] = str(tags[tag][0])
                                break
        except Exception as e:
            print(f"Error extracting metadata from {filepath}: {e}")
            
        # Extract from filename if metadata is missing
        if 'title' not in metadata or not metadata['title'] or 'artist' not in metadata or not metadata['artist']:
            track = Track(filepath=filepath)
            
            if 'title' not in metadata or not metadata['title']:
                metadata['title'] = track._extract_title_from_path(filepath)
                
            if 'artist' not in metadata or not metadata['artist']:
                metadata['artist'] = track._extract_artist_from_path(filepath)
                
        return metadata

def scan_directories(directories: List[str]) -> MediaScanner:
    """
    Helper function to create and return a media scanner.
    
    Args:
        directories: List of directories to scan
        
    Returns:
        MediaScanner instance ready to be started in a thread
    """
    scanner = MediaScanner(directories)
    return scanner

def process_file(filepath: str):
    """Extract metadata from a single file and add to DB."""
    try:
        # Extract metadata
        metadata = extract_metadata(filepath)
        
        # Create Track object from metadata
        track = Track(
            filepath=filepath,
            title=metadata.get('title'),
            artist=metadata.get('artist'),
            album=metadata.get('album'),
            genre=metadata.get('genre'),
            length=metadata.get('length'),
            album_art=metadata.get('album_art')
        )
        
        # If title is missing, extract from filename (YouTube style parsing)
        if not track.title:
            track.title = track._extract_title_from_path(filepath)
            
        # If artist is missing, extract from filename (YouTube style parsing)
        if not track.artist:
            track.artist = track._extract_artist_from_path(filepath)
        
        # Insert or update track in database
        print(f"Adding to database: {track.title} - {track.artist}")
        database.add_or_update_track(track)
        return True

    except Exception as e:
        error_msg = f"Error processing file: {filepath}"
        print(error_msg)
        print(f"Exception: {e}")
        return False

def extract_metadata(filepath: str):
    """Extract metadata from an audio file."""
    metadata = {}
    try:
        audio = MutagenFile(filepath)
        if audio is None:
            return metadata
        
        # Common fields
        if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
            metadata['length'] = audio.info.length
            
        # Handle MP3 files with ID3 tags
        if isinstance(audio, MP3):
            if 'TIT2' in audio:
                metadata['title'] = str(audio['TIT2'])
            if 'TPE1' in audio:
                metadata['artist'] = str(audio['TPE1'])
            print(f"Could not read metadata (audio is None): {filepath}")
            # Fallback for formats easy=True might miss (less common)
            try:
                audio_raw = MutagenFile(filepath)
                if not audio_raw: 
                    print(f"Still couldn't read file as audio: {filepath}")
                    return False
                
                # Special handling for MP4 files since they might not work with easy=True
                if filepath.lower().endswith(('.mp4', '.m4a', '.m4b', '.m4p', '.m4v')):
                    print(f"Attempting special MP4 handling for: {filepath}")
                    return process_mp4_file(filepath, audio_raw)
                    
                # Manual extraction needed here if easy=True failed
                print(f"Falling back to manual metadata extraction for: {filepath}")
                # For now, just skip if easy=True fails and audio is None
                return False
            except (MutagenError, ID3NoHeaderError) as e:
                print(f"Skipping file (MutagenError fallback: {e}): {filepath}")
                return False
            except Exception as e_fallback:
                print(f"Skipping file (Unknown fallback error: {e_fallback}): {filepath}")
                return False

        # Special handling for MP4 files even if they worked with easy=True
        if isinstance(audio, MP4) or filepath.lower().endswith(('.mp4', '.m4a', '.m4b', '.m4p', '.m4v')):
            print(f"Using MP4-specific handling for: {filepath}")
            return process_mp4_file(filepath, audio)

        track = Track(filepath=filepath)

        # Common tags (using 'easy' interface keys)
        track.title = get_tag(audio, 'title')
        track.artist = get_tag(audio, 'artist')
        track.album = get_tag(audio, 'album')
        track.genre = get_tag(audio, 'genre')

        track_num_str = get_tag(audio, 'tracknumber')
        if track_num_str:
            try:
                # Handle "track/total" format
                track.track_number = int(track_num_str.split('/')[0])
            except (ValueError, IndexError):
                track.track_number = None

        year_str = get_tag(audio, 'date') # Often contains full date
        if year_str:
            try:
                track.year = int(year_str[:4]) # Extract year
            except (ValueError, IndexError):
                 # Try 'year' tag as fallback
                 year_str_alt = get_tag(audio, 'year')
                 if year_str_alt:
                     try: track.year = int(year_str_alt[:4])
                     except (ValueError, IndexError): track.year = None
                 else:
                     track.year = None


        if audio.info:
            track.duration = audio.info.length
        else: # Fallback for duration if info is missing
            duration_alt = get_tag(audio, 'length') # Some formats might have this
            if duration_alt:
                try: track.duration = float(duration_alt)
                except ValueError: track.duration = None


        # Extract Album Art (more complex - requires format-specific checks)
        try:
            # Re-open with easy=False to access picture details if needed
            audio_raw = MutagenFile(filepath)
            if isinstance(audio_raw, (MP3, FLAC)):
                if isinstance(audio_raw, MP3):
                    pics = audio_raw.tags.getall('APIC') if audio_raw.tags else []
                elif isinstance(audio_raw, FLAC):
                     pics = audio_raw.pictures
                else: pics = []

                if pics:
                    # Prefer front cover (type 3)
                    front_cover = next((p for p in pics if p.type == 3), None)
                    if front_cover:
                        track.album_art = front_cover.data
                    elif pics: # Fallback to first picture found
                        track.album_art = pics[0].data

            elif isinstance(audio_raw, MP4): # M4A files
                if 'covr' in audio_raw.tags:
                    covers = audio_raw.tags['covr']
                    if covers:
                        track.album_art = covers[0] # MP4 stores cover as bytes directly

            elif isinstance(audio_raw, OggVorbis):
                # Vorbis comments store cover art base64 encoded in specific tags
                metadata_tags = audio_raw.tags.get('metadata_block_picture', [])
                if metadata_tags:
                    import base64
                    from mutagen.flac import Picture # Vorbis uses FLAC Picture structure
                    try:
                        # Decode base64 data
                        pic_data = base64.b64decode(metadata_tags[0])
                        # Parse the Picture structure
                        picture = Picture(pic_data)
                        track.album_art = picture.data
                    except (ImportError, base64.binascii.Error, Exception) as e_vorbis:
                         print(f"Error decoding Vorbis cover art for {filepath}: {e_vorbis}")


        except AttributeError:
             # Some formats might not have 'pictures' or 'tags' attribute as expected
             pass
        except (MutagenError, ID3NoHeaderError):
            # Handle cases where reading raw tags fails
            pass
        except Exception as e_art:
             print(f"Error extracting album art for {filepath}: {e_art}")


        # Add to database
        print(f"Adding to database: {track.title} - {track.artist}")
        database.add_or_update_track(track)
        return True

    except ID3NoHeaderError:
        print(f"Skipping file (No ID3 Header): {filepath}")
        return False
    except MutagenError as e:
        """Scans the directory, extracts metadata, and adds to DB."""
        print(f"ScannerWorker started for directory: {self.music_dir}")
        found_files = []
        processed_count = 0
        try:
            # First pass: Find all potential audio files
            print(f"Beginning file search in {self.music_dir}")
            for root, dirs, files in os.walk(self.music_dir):
                if self._is_cancelled:
                    print("Scan cancelled during file discovery.")
                    self.signals.scan_finished.emit(0) # Indicate cancellation
                    return

                # Debug: Print the directories being scanned
                print(f"Scanning directory: {root}")
                print(f"Found {len(files)} files in this directory")
                
                for filename in files:
                    extension = os.path.splitext(filename)[1].lower()
                    if extension in SUPPORTED_EXTENSIONS:
                        filepath = os.path.join(root, filename)
                        found_files.append(filepath)
                        print(f"Found music file: {filepath}")
                    else:
                        # Debug which extensions are being skipped
                        if extension:
                            print(f"Skipping unsupported file type: {extension} - {filename}")

            total_files = len(found_files)
            print(f"Found {total_files} potential audio files.")
            if total_files == 0:
                print("No audio files found. Check your music directory and file types.")
                self.signals.error_occurred.emit("No music files found. Check your music directory.")
            
            self.signals.progress_updated.emit(0, total_files) # Initial progress

            # Second pass: Process each file
            for filepath in found_files:
                 if self._is_cancelled:
                    print("Scan cancelled during processing.")
                    break # Exit loop

                 print(f"Processing file: {filepath}")
                 success = self.process_file(filepath)
                 if success:
                     print(f"Successfully processed: {filepath}")
                 processed_count += 1
                 if processed_count % 20 == 0 or processed_count == total_files: # Update progress periodically
                    self.signals.progress_updated.emit(processed_count, total_files)

            if not self._is_cancelled:
                # Optional: Clean up DB - remove tracks whose files no longer exist
                print("Cleaning up database...")
                database.remove_tracks_not_in_list(found_files)
                print("Database cleanup finished.")

        except Exception as e:
            error_msg = f"Error during scanning: {e}"
            print(error_msg)
            self.signals.error_occurred.emit(error_msg)
            self.signals.scan_finished.emit(processed_count) # Finish with count so far
            return # Exit on major error

        if not self._is_cancelled:
            print(f"ScannerWorker finished. Processed {processed_count} files.")
            self.signals.scan_finished.emit(processed_count)
        else:
             print("ScannerWorker finished due to cancellation.")
             self.signals.scan_finished.emit(0) # Indicate cancellation


    def process_file(self, filepath: str):
        """Extract metadata from a single file and add to DB."""
        try:
            # Extract metadata
            metadata = self.extract_metadata(filepath)
            
            # Create Track object from metadata
            track = Track(
                filepath=filepath,
                title=metadata.get('title'),
                artist=metadata.get('artist'),
                album=metadata.get('album'),
                genre=metadata.get('genre'),
                length=metadata.get('length'),
                album_art=metadata.get('album_art')
            )
            
            # If title is missing, extract from filename (YouTube style parsing)
            if not track.title:
                track.title = track._extract_title_from_path(filepath)
                
            # If artist is missing, extract from filename (YouTube style parsing)
            if not track.artist:
                track.artist = track._extract_artist_from_path(filepath)
            
            # Insert or update track in database
            print(f"Adding to database: {track.title} - {track.artist}")
            database.add_or_update_track(track)
            return True

        except Exception as e:
            error_msg = f"Error processing file: {filepath}"
            print(error_msg)
            print(f"Exception: {e}")
            self.signals.error_occurred.emit(error_msg)
            self.signals.scan_finished.emit(processed_count) # Finish with count so far
            return False

    def extract_metadata(self, filepath: str):
        """Extract metadata from an audio file."""
        metadata = {}
        try:
            audio = MutagenFile(filepath)
            if audio is None:
                return metadata
            
            # Common fields
            if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                metadata['length'] = audio.info.length
                
            # Handle MP3 files with ID3 tags
            if isinstance(audio, MP3):
                if 'TIT2' in audio:
                    metadata['title'] = str(audio['TIT2'])
                if 'TPE1' in audio:
                    metadata['artist'] = str(audio['TPE1'])
                print(f"Could not read metadata (audio is None): {filepath}")
                # Fallback for formats easy=True might miss (less common)
                try:
                    audio_raw = MutagenFile(filepath)
                    if not audio_raw: 
                        print(f"Still couldn't read file as audio: {filepath}")
                        return False
                    
                    # Special handling for MP4 files since they might not work with easy=True
                    if filepath.lower().endswith(('.mp4', '.m4a', '.m4b', '.m4p', '.m4v')):
                        print(f"Attempting special MP4 handling for: {filepath}")
                        return self.process_mp4_file(filepath, audio_raw)
                        
                    # Manual extraction needed here if easy=True failed
                    print(f"Falling back to manual metadata extraction for: {filepath}")
                    # For now, just skip if easy=True fails and audio is None
                    return False
                except (MutagenError, ID3NoHeaderError) as e:
                    print(f"Skipping file (MutagenError fallback: {e}): {filepath}")
                    return False
                except Exception as e_fallback:
                    print(f"Skipping file (Unknown fallback error: {e_fallback}): {filepath}")
                    return False

            # Special handling for MP4 files even if they worked with easy=True
            if isinstance(audio, MP4) or filepath.lower().endswith(('.mp4', '.m4a', '.m4b', '.m4p', '.m4v')):
                print(f"Using MP4-specific handling for: {filepath}")
                return self.process_mp4_file(filepath, audio)

            track = Track(filepath=filepath)

            # Common tags (using 'easy' interface keys)
            track.title = self.get_tag(audio, 'title')
            track.artist = self.get_tag(audio, 'artist')
            track.album = self.get_tag(audio, 'album')
            track.genre = self.get_tag(audio, 'genre')

            track_num_str = self.get_tag(audio, 'tracknumber')
            if track_num_str:
                try:
                    # Handle "track/total" format
                    track.track_number = int(track_num_str.split('/')[0])
                except (ValueError, IndexError):
                    track.track_number = None

            year_str = self.get_tag(audio, 'date') # Often contains full date
            if year_str:
                try:
                    track.year = int(year_str[:4]) # Extract year
                except (ValueError, IndexError):
                     # Try 'year' tag as fallback
                     year_str_alt = self.get_tag(audio, 'year')
                     if year_str_alt:
                         try: track.year = int(year_str_alt[:4])
                         except (ValueError, IndexError): track.year = None
                     else:
                         track.year = None


            if audio.info:
                track.duration = audio.info.length
            else: # Fallback for duration if info is missing
                duration_alt = self.get_tag(audio, 'length') # Some formats might have this
                if duration_alt:
                    try: track.duration = float(duration_alt)
                    except ValueError: track.duration = None


            # Extract Album Art (more complex - requires format-specific checks)
            try:
                # Re-open with easy=False to access picture details if needed
                audio_raw = MutagenFile(filepath)
                if isinstance(audio_raw, (MP3, FLAC)):
                    if isinstance(audio_raw, MP3):
                        pics = audio_raw.tags.getall('APIC') if audio_raw.tags else []
                    elif isinstance(audio_raw, FLAC):
                         pics = audio_raw.pictures
                    else: pics = []

                    if pics:
                        # Prefer front cover (type 3)
                        front_cover = next((p for p in pics if p.type == 3), None)
                        if front_cover:
                            track.album_art = front_cover.data
                        elif pics: # Fallback to first picture found
                            track.album_art = pics[0].data

                elif isinstance(audio_raw, MP4): # M4A files
                    if 'covr' in audio_raw.tags:
                        covers = audio_raw.tags['covr']
                        if covers:
                            track.album_art = covers[0] # MP4 stores cover as bytes directly

                elif isinstance(audio_raw, OggVorbis):
                    # Vorbis comments store cover art base64 encoded in specific tags
                    metadata_tags = audio_raw.tags.get('metadata_block_picture', [])
                    if metadata_tags:
                        import base64
                        from mutagen.flac import Picture # Vorbis uses FLAC Picture structure
                        try:
                            # Decode base64 data
                            pic_data = base64.b64decode(metadata_tags[0])
                            # Parse the Picture structure
                            picture = Picture(pic_data)
                            track.album_art = picture.data
                        except (ImportError, base64.binascii.Error, Exception) as e_vorbis:
                             print(f"Error decoding Vorbis cover art for {filepath}: {e_vorbis}")


            except AttributeError:
                 # Some formats might not have 'pictures' or 'tags' attribute as expected
                 pass
            except (MutagenError, ID3NoHeaderError):
                # Handle cases where reading raw tags fails
                pass
            except Exception as e_art:
                 print(f"Error extracting album art for {filepath}: {e_art}")


            # Add to database
            print(f"Adding to database: {track.title} - {track.artist}")
            database.add_or_update_track(track)
            return True

        except ID3NoHeaderError:
            print(f"Skipping file (No ID3 Header): {filepath}")
            return False
        except MutagenError as e:
            print(f"Skipping file (MutagenError: {e}): {filepath}")
            self.signals.error_occurred.emit(f"Metadata error in {os.path.basename(filepath)}")
            return False
        except Exception as e: # Catch broader errors during processing
             print(f"Skipping file (Unexpected Error: {e}): {filepath}")
             self.signals.error_occurred.emit(f"Error processing {os.path.basename(filepath)}")
             return False
             
    def process_mp4_file(self, filepath: str, audio):
        """Special handling for MP4 files which use different tag names"""
        try:
            track = Track(filepath=filepath)
            
            # MP4 uses different atom names for tags
            mp4_tag_mapping = {
                'title': ['©nam', 'name', '©tit'],  # Title tag variants 
                'artist': ['©ART', '©art', 'aART', 'artist'],  # Artist tag variants
                'album': ['©alb', 'album'],  # Album tag variants
                'genre': ['©gen', 'gnre', 'genre'],  # Genre tag variants
                'date': ['©day', 'year'],  # Date/year tag variants
                'tracknumber': ['trkn']  # Track number tag
            }
            
            print(f"MP4 file tags: {list(audio.tags.keys()) if hasattr(audio, 'tags') and audio.tags else 'No tags'}")
            
            # Extract basic metadata
            if hasattr(audio, 'tags') and audio.tags:
                # Title
                for tag in mp4_tag_mapping['title']:
                    if tag in audio.tags:
                        track.title = str(audio.tags[tag][0])
                        break
                        
                # Artist
                for tag in mp4_tag_mapping['artist']:
                    if tag in audio.tags:
                        track.artist = str(audio.tags[tag][0])
                        break
                        
                # Album
                for tag in mp4_tag_mapping['album']:
                    if tag in audio.tags:
                        track.album = str(audio.tags[tag][0])
                        break
                        
                # Genre
                for tag in mp4_tag_mapping['genre']:
                    if tag in audio.tags:
                        # Genre in MP4 can be an index or string
                        genre_value = audio.tags[tag][0]
                        if isinstance(genre_value, int):
                            # Convert genre ID to string if needed
                            # This is simplified; a real impl might use a genre lookup table
                            track.genre = f"Genre {genre_value}"
                        else:
                            track.genre = str(genre_value)
                        break
                
                # Year
                for tag in mp4_tag_mapping['date']:
                    if tag in audio.tags:
                        year_str = str(audio.tags[tag][0])
                        try:
                            # Extract first 4 digits as year
                            track.year = int(year_str[:4])
                            break
                        except (ValueError, IndexError):
                            continue
                
                # Track number
                if 'trkn' in audio.tags:
                    try:
                        # MP4 stores track number as tuple (track, total)
                        track.track_number = audio.tags['trkn'][0][0]
                    except (IndexError, TypeError):
                        track.track_number = None
            
            # If title is still None, use filename as fallback
            if not track.title:
                track.title = os.path.splitext(os.path.basename(filepath))[0]
                
            # Duration
            if hasattr(audio, 'info') and audio.info:
                track.duration = audio.info.length
            
            # Album art
            if hasattr(audio, 'tags') and audio.tags and 'covr' in audio.tags:
                covers = audio.tags['covr']
                if covers:
                    track.album_art = covers[0]  # MP4 stores cover as bytes directly
            
            # Add to database
            print(f"Adding MP4 to database: {track.title} - {track.artist}")
            database.add_or_update_track(track)
            return True
            
        except Exception as e:
            print(f"Error processing MP4 file {filepath}: {e}")
            self.signals.error_occurred.emit(f"Error processing MP4 file: {os.path.basename(filepath)}")
            return False

    def get_tag(self, audio, tag_name):
        """Safely get a tag value from easy=True Mutagen object."""
        tag_value = audio.get(tag_name)
        if tag_value:
            # Mutagen often returns lists, get the first element
            return str(tag_value[0]) if isinstance(tag_value, list) else str(tag_value)
        return None

    def cancel(self):
        """Signals the worker to stop scanning."""
        print("ScannerWorker cancel requested.")
        self._is_cancelled = True