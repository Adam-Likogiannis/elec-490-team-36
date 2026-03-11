import numpy as np
from PIL import Image
import embed_new
import cameraEmbed

def decode_image(inputpath):
    step = 30
    key = ""
    message = embed_new.decode_image(inputpath, step, key)

def watermark_image(message, inputpath, outputpath):
    step = 30
    key = ""
    quality = 95
    embed_new.apply_watermark_to_camera_image(message, step, key, inputpath, outputpath, quality)



def watermark_image_new(message, inputpath, outputpath):
    step = 30
    key = None
    quality = 95
    cameraEmbed.watermark_camera_image(message, step, key, inputpath, outputpath, quality)


def decode_image_new(inputpath):
    step = 30
    key = ""
    message = cameraEmbed.decode_image(inputpath, step, key)

def process_image_pct(input_path, output_path, crop_pct=10, degrees=15, sigma=0.05, quality = 85):
    with Image.open(input_path) as img:
        w, h = img.size
        
        # Calculate Crop Coordinates
        margin_w = (crop_pct / 100) * w / 2
        margin_h = (crop_pct / 100) * h / 2
        
        box = (margin_w, margin_h, w - margin_w, h - margin_h)
        cropped_img = img.crop(box)

        # Rotate 
        rotated_img = cropped_img.rotate(degrees, expand=True)

        # Add Gaussian Noise
        img_array = np.array(rotated_img).astype(np.float32)
        noise = np.random.normal(0, sigma, img_array.shape)
        noisy_img = np.clip(img_array + noise, 0, 255).astype(np.uint8)

        final_img = Image.fromarray(noisy_img)
        final_img.save(output_path, "JPEG", quality=quality)
        
        # Save
        Image.fromarray(noisy_img).save(output_path)
        print(f"Success!")

if __name__ == "__main__":
    file_name = "lights_watermarked.jpg"
    input_image = "./Old_Images/" + file_name
    output_image ="./Robust_test/lights_compression.jpg" 

    #watermark_image("YAY MESESAGE", input_image, output_image)
    #process_image_pct(input_image, output_image, crop_pct=0, degrees=0, sigma=0.05)
    #decode_image(output_image)
    
    #watermark_image_new("YAY MESESAGE", input_image, output_image)
    process_image_pct(input_image, output_image, crop_pct=0, degrees=0, sigma=0, quality = 85)
    decode_image_new(output_image)
    
    
