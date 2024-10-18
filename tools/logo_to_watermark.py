import cv2
import numpy as np
from argparse import ArgumentParser
import os
import sys



def get_args():
    parser = ArgumentParser(prog='Logo to Watermark Converter',
                    description='Adds an alpha channel to an image, removes the background, and creates a contrasting shadow')
                    
    parser.add_argument("-c", "--bkg_color", default="ffffff",
                        help="6-digit hex string to use as background color (000000 for black, ffffff for white)")
    
    parser.add_argument("-d", "--dim", default=1000, type=int,
                        help="Resize larger dimension of image to this size")

    parser.add_argument("-i", "--input_path",
                        help="Path to input image")
    
    parser.add_argument("-o", "--output_path",
                        help="Path to save output image")
    
    parser.add_argument("--diff_min", default=0.1, type=float,
                        help="Min difference from background color which will be considered foreground")
    
    parser.add_argument("--diff_max", default=0.9, type=float,
                        help="Max difference from background color which will be considered background")
    
    parser.add_argument("--shadow_size", default=15, type=int,
                        help="Shadow size")
    
    parser.add_argument("--shadow_opacity", default=1.5, type=float,
                        help="Shadow opacity")
    
    parser.add_argument("--shadow_offset", default=5, type=int,
                        help="Shadow offset (downward and to the right)")
    
    parser.add_argument("--force_rgb", action="store_true",
                        help="Ignore input image alpha channel, even if present")
    
    return parser.parse_args()


def hex_to_rgb(hex_code):
    # Remove the '#' if it's present
    hex_code = hex_code.lstrip('#')
    
    # Convert the hex string to three integers
    red = int(hex_code[0:2], 16)
    green = int(hex_code[2:4], 16)
    blue = int(hex_code[4:6], 16)
    
    return red, green, blue


def get_background(logo, background_color):
    r, g, b = background_color
    float_bkg = np.zeros_like(logo)
    float_bkg[:,:] = [r, g, b]
    return float_bkg


def get_foreground(image, background_color):
    br, bg, bb = background_color
    r = 255 - br
    g = 255 - bg
    b = 255 - bb
    float_fg = np.zeros_like(image)
    float_fg[:,:] = [r, g, b]
    return float_fg


def get_foreground_mask(image, diff_min, diff_max, background):
    float_image = image.astype(np.float32)

    diff_rgb = background - float_image

    diff = np.linalg.norm(diff_rgb, axis=2) / 255.0
    diff_scaled = (diff - diff_min) / (diff_max - diff_min)
    diff_clip = np.clip(diff_scaled, a_min=0, a_max=1)

    return diff_clip


def create_shadow(foreground_mask, blur_radius, opacity):
    kernel_size = (blur_radius * 2) + 1
    shadow = cv2.GaussianBlur(foreground_mask,(kernel_size,kernel_size),0)
    shadow *= opacity
    return shadow
    

def showimage(image):
    cv2.imshow("Foo", image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def composite_images(alpha, foreground, background):
    channels = foreground.shape[2]
    mask_chan = np.stack([alpha]*channels, -1)
    mask_chan_inv = np.ones_like(mask_chan) - mask_chan
    im_1 = foreground * mask_chan
    im_2 = background * mask_chan_inv
    composite = im_1 + im_2
    return composite


def apply_shadow(logo, foreground_mask, shadow, background, offset):
    composite = composite_images(foreground_mask, logo, background)

    if offset > 0:
        shadow_crop = shadow[:-1*offset, :-1*offset]
        mask_crop = foreground_mask[offset:, offset:]
        alpha = foreground_mask.copy()
        alpha[offset:,offset:] = shadow_crop + mask_crop
    else:
        alpha = shadow + foreground_mask

    alpha = np.clip(alpha, a_min=0, a_max=1.0)
    alpha = alpha * 255.0

    final_image = np.stack(
        [
            composite[:,:,0],
            composite[:,:,1],
            composite[:,:,2],
            alpha
        ],
        -1)

    return final_image
    

def resize_to(image, dim):
    height, width, _ = image.shape
    print(f"Original image dimensions: {width} W x {height} H", image.shape)
    aspect_ratio = width / height
    if width > height:
        new_width = dim
        new_height = int(dim / aspect_ratio)
    else:
        new_width = int(dim * aspect_ratio)
        new_height = dim

    new_dims = (new_width, new_height)

    new_image = cv2.resize(image, new_dims, cv2.INTER_CUBIC)

    height, width, _ = new_image.shape

    print(f"New image dimensions: {width} W x {height} H", new_image.shape)
    return new_image


def pad_image(image, rad, offset):
    border_type = cv2.BORDER_CONSTANT
    if len(image.shape) == 2:
        value = 0
    else:
        value = [0] * image.shape[2]
    top = rad
    bottom = rad + offset
    left = rad
    right = rad + offset
    padded_image = cv2.copyMakeBorder(image, top, bottom, left, right, border_type, value=value)
    return padded_image

    
if __name__ == "__main__":
    args = get_args()

    image_raw = cv2.imread(args.input_path, cv2.IMREAD_UNCHANGED)

    if np.amax(image_raw) > 255:
        image_raw = image_raw / (np.amax(image_raw) / 255)

    image = resize_to(image_raw, dim=args.dim)

    showimage(image)

    logo = image[:,:,:3].astype(np.float32)
        
    background_color = hex_to_rgb(args.bkg_color)
    background = get_background(logo, background_color)

    if (image.shape[2] == 3) or args.force_rgb:
        print("Detecting background from RGB image")
        foreground_mask = get_foreground_mask(logo, args.diff_min, args.diff_max, background)
    elif image.shape[2] == 4:
        print("Using alpha from image with transparency") 
        foreground_mask = image[:,:,3].astype(np.float32) / 255.0

    showimage(foreground_mask)

    padded_mask = pad_image(foreground_mask, args.shadow_size, args.shadow_offset)
    padded_logo = pad_image(logo, args.shadow_size, args.shadow_offset)
    padded_background = get_background(padded_logo, background_color)

    shadow = create_shadow(padded_mask, blur_radius=args.shadow_size, opacity=args.shadow_opacity)

    showimage(shadow)

    final_image = apply_shadow(padded_logo, padded_mask, shadow, padded_background, args.shadow_offset)

    output_path = args.output_path
    if os.path.isdir(output_path):
        output_path += "/converted_watermark.png"
    cv2.imwrite(output_path, final_image)

    foreground = get_foreground(final_image[:,:,:3], background_color)
    example_image = composite_images(final_image[:,:,3] / 255, final_image[:,:,:3], foreground)

    showimage(example_image / 255)
