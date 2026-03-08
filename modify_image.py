from PIL import Image

def adjust_red_channel(image_path, factor, image_name):
    """Reduces the red channel in an image."""
    with Image.open(image_path) as img:
        r, g, b = img.split()
        # Reduce red channel intensity
        r = r.point(lambda p: p * factor)
        g = g.point(lambda g: g * factor)
        # Merge back
        Image.merge('RGB', (r, g, b)).save(image_path)
