import cv2
import numpy as np

class PrintFormatter:
    def __init__(self, print_format, h_crop_2x6=0.9, **kwargs):
        self.print_format = print_format
        if print_format == "4x3":
            self._num_photos = 2
            self._media = "custom_119.21x156.15mm_119.21x156.15mm"
        elif self.print_format == "2x6":
            self._num_photos = 3
            self._media = "custom_119.21x155.45mm_119.21x155.45mm"
            self._h_crop = h_crop_2x6
            
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
            cv2.imwrite(file_path, out_image)
        elif self.print_format == "2x6":
            image_aspect_ratio = 3801/2778
            image_h_crop = self._h_crop
            cropped_aspect_ratio = image_aspect_ratio * image_h_crop
            image_width = 600
            image_height = int(image_width / (image_aspect_ratio * image_h_crop))
            canvas_width = image_width
            canvas_height = image_width * 3
            y_padding = int((image_width - image_height) / 2)
            canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255
            y = 0
            for (i, image_path) in enumerate(image_paths):
                image = cv2.imread(image_path)
                crop_x1 = int(image.shape[1] * (1 - image_h_crop) / 2)
                crop_x2 = crop_x1 + int(image.shape[1] * image_h_crop)
                image = image[:, crop_x1:crop_x2, :]
                resized = cv2.resize(image, (image_width, image_height))
                canvas[y + y_padding : y + y_padding + image_height, :, :] = resized
                y += image_width
            cv2.imwrite(preview_path, canvas)
            out_image = cv2.hconcat([canvas, canvas])
            out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
            cv2.imwrite(file_path, out_image)
        return file_path, preview_path
