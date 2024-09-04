import cv2
import numpy as np
from common.common import load_config

class PrintFormatter:
    def __init__(self, print_format, h_crop_2x6=1, h_pad=0, **kwargs):
        self.print_format = print_format
        self.h_pad = 0.04
        
        self.logo = None
        self.logo_width_scale = -1
        try:
            logo_config = load_config("print_logo_config.yaml")
        except FileNotFoundError:
            logo_config = None
        if logo_config:
            if logo_config["enable"]:
                self.logo = cv2.imread(logo_config["logo_path"])
                self.logo_width_scale = logo_config["logo_width_scale"]
        
        if print_format == "4x3":
            self._num_photos = 2
            self._media = "custom_119.21x156.15mm_119.21x156.15mm"
        elif self.print_format == "2x6":
            self._num_photos = 3
            self._media = "custom_119.21x155.45mm_119.21x155.45mm"
            self._h_crop = h_crop_2x6
        if print_format == "3x2":
            self._num_photos = 4
            self._media = "custom_119.21x156.15mm_119.21x156.15mm"
            
    def num_photos(self):
        return self._num_photos
        
    def print_options(self):
        options = {
            "media": self._media
        }
        return options

    def format_print(self, image_paths):
        preview_path = "preview.png"
        file_path = "formatted.jpg"
        
        if self.print_format == "4x3":
            images = []
            for image_path in image_paths:
                image = cv2.imread(image_path)
                images.append(image)
            out_image = cv2.vconcat(images)
            preview_image = cv2.resize(out_image, (400, 600))
            cv2.imwrite(preview_path, preview_image)
            out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
            
        elif self.print_format == "2x6":
            image_aspect_ratio = 3801/2778
            image_h_crop = self._h_crop
            cropped_aspect_ratio = image_aspect_ratio * image_h_crop
            
            image_width = 600
            image_height = int(image_width / (image_aspect_ratio * image_h_crop))
            
            canvas_width = image_width
            canvas_height = image_width * 3
            
            if self.logo is not None:
                logo_aspect = self.logo.shape[1] / self.logo.shape[0]
                logo_width = int(canvas_width * self.logo_width_scale)
                logo_height = int(logo_width / logo_aspect)
                logo_x_offset = int((canvas_width - logo_width) / 2)
                logo = cv2.resize(self.logo, (logo_width, logo_height))
                y_padding = int((canvas_height - (image_height * 3) - logo_height) / 5)
            else:
                y_padding = int((canvas_height - (image_height * 3)) / 4)
            
            canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255
            y = y_padding
            for (i, image_path) in enumerate(image_paths):
                image = cv2.imread(image_path)
                crop_x1 = int(image.shape[1] * (1 - image_h_crop) / 2)
                crop_x2 = crop_x1 + int(image.shape[1] * image_h_crop)
                image = image[:, crop_x1:crop_x2, :]
                resized = cv2.resize(image, (image_width, image_height))
                canvas[y : y + image_height, :, :] = resized
                y += y_padding + image_height
                
            if self.logo is not None:
                canvas[y : y + logo_height, logo_x_offset:logo_x_offset + logo_width, :] = logo
                
            cv2.imwrite(preview_path, canvas)
            out_image = cv2.hconcat([canvas, canvas])
            out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
        
        elif self.print_format == "3x2":
            aspect_ratio = 3/2
        
            images = []
            for image_path in image_paths:
                image = cv2.imread(image_path)
                crop_h = int(image.shape[1] / aspect_ratio)
                crop_y = int((image.shape[0] - crop_h) / 2)
                cropped = image[crop_y : crop_y + crop_h, :, :]
                images.append(cropped)
                
            stacks = []
            for i in range(0, 4, 2):
                stack = cv2.vconcat([images[i], images[i + 1]])
                stacks.append(stack)
                
            out_image = cv2.hconcat(stacks)
            preview_image = cv2.resize(out_image, (600, 400))
            cv2.imwrite(preview_path, preview_image)
            out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
            
        if self.h_pad:
            image_height = out_image.shape[0]
            image_width = out_image.shape[1]
            pad_height = int((image_height * self.h_pad) / 2)
            pad = np.ones((pad_height, image_width, 3), dtype=np.uint8) * 255
            out_image = cv2.vconcat([pad, out_image, pad])
        cv2.imwrite(file_path, out_image)
        return file_path, preview_path
        
if __name__ == "__main__":
    formatter = PrintFormatter(
            print_format = "2x6",
            h_crop_2x6 = 0.9,
            h_pad = 0,
            logo_path = "/home/patecolin/photobooth_site/watermarks/aa-no-circle_logo_edited.png",
            logo_width_scale = 0.6
        )
    import glob
    images = glob.glob("/home/patecolin/photobooth_site/print_examples/*.jpg")
   
    formatter.format_print(images)
    
