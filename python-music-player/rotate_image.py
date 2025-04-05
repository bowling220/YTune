from PIL import Image
import os

# Define file paths
icons_dir = os.path.join('assets', 'icons')
input_file = os.path.join(icons_dir, 'next (1).png')
output_file = os.path.join(icons_dir, 'next1.png')

# Make sure the input file exists
if not os.path.isfile(input_file):
    print(f"Input file not found: {input_file}")
    # List the files in the directory
    print(f"Files in {icons_dir}:")
    try:
        for file in os.listdir(icons_dir):
            print(f"  - {file}")
    except Exception as e:
        print(f"Error listing directory: {e}")
    exit(1)

# Open the original image
try:
    img = Image.open(input_file)
    print(f"Opened image: {input_file}")

    # Rotate the image 180 degrees
    rotated_img = img.rotate(180)
    
    # Save the rotated image
    rotated_img.save(output_file)
    print(f"Saved rotated image to: {output_file}")
    
    print("Image rotation complete!")
except Exception as e:
    print(f"Error: {e}") 