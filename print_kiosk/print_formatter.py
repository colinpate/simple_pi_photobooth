import cv2
import numpy as np

class PrintFormatter:
    def __init__(self, print_format, h_crop_2x6=1, v_crop_2x6=1, h_pad=0, watermark=None, **kwargs):
        self.print_format = print_format
        self.h_pad = h_pad
        self.test_mode = True
        
        self.logo = None
        self.logo_width_scale = -1
        if watermark:
            if watermark["enable"]:
                self.logo = cv2.imread(watermark["watermark_path"])
                self.logo_width_scale = watermark["logo_width_scale"]
        
        if print_format == "4x3":
            self._num_photos = 2
            self._media = "custom_119.21x156.15mm_119.21x156.15mm"
        elif print_format == "Polaroid":
            self._num_photos = 2
            self._media = "custom_119.21x156.15mm_119.21x156.15mm"
        elif self.print_format == "2x6":
            self._num_photos = 3
            self._media = "custom_119.21x155.45mm_119.21x155.45mm"
            self._h_crop = h_crop_2x6
            self._v_crop = v_crop_2x6
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

    def resize_logo(self, canvas_width):
        logo_aspect = self.logo.shape[1] / self.logo.shape[0]
        logo_width = int(canvas_width * self.logo_width_scale)
        logo_height = int(logo_width / logo_aspect)
        logo_x_offset = int((canvas_width - logo_width) / 2)
        logo = cv2.resize(self.logo, (logo_width, logo_height))
        return logo_width,logo_height,logo_x_offset,logo

    def format_print(self, image_paths):
        def crop_image(image, x_ratio=1, y_ratio=1):
            crop_x1 = int(image.shape[1] * (1 - x_ratio) / 2)
            crop_x2 = crop_x1 + int(image.shape[1] * x_ratio)
            crop_y1 = int(image.shape[0] * (1 - y_ratio) / 2)
            crop_y2 = crop_x1 + int(image.shape[0] * y_ratio)
            cropped = image[crop_y1:crop_y2, crop_x1:crop_x2, :]
            return cropped
    
        images = [cv2.imread(im_path) for im_path in image_paths]
        image_shape = images[0].shape
        for image in images[1:]:
            if image.shape != image_shape:
                raise ValueError("Images must all be the same dimensions ", image_shape, image.shape)
            
        if self.print_format == "4x3":
            out_image = cv2.vconcat(images)
            preview_image = cv2.resize(out_image, (400, 600))
            out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)

        elif self.print_format == "Polaroid":
            canvas_width = 1200
            canvas_height = 1600
            resized_width = int(canvas_width * 0.9)
            resized_height = resized_width
            canvasses = []
            for i in range(self._num_photos):
                canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255

                image = images[i]
                cropped = crop_image(image, x_ratio = image_shape[0] / image_shape[1])
                print(cropped.shape)

                resized = cv2.resize(cropped, (resized_width, resized_height))
                print(resized.shape)

                x_offset = int((canvas_width - resized_width) / 2)
                y_offset = int(x_offset * 1.5) # arbitrary
                image_bottom = y_offset + resized_height
                canvas[y_offset:image_bottom, x_offset:x_offset + resized_width, :] = resized

                if self.logo is not None:
                    logo_width, logo_height, logo_x_offset, logo = self.resize_logo(canvas_width)
                    logo_v_center = int((image_bottom + canvas_height) / 2)
                    logo_top = int(logo_v_center - (logo_height / 2))
                    logo_bottom = logo_top + logo_height
                    if logo_bottom >= canvas_height:
                        raise ValueError("Logo is too tall. Try decreasing logo_width_scale")
                    logo_left = int((canvas_width - logo_width) / 2)
                    logo_right = logo_left + logo_width
                    canvas[logo_top : logo_bottom, logo_left:logo_right, :] = logo

                if self.test_mode:
                    cv2.rectangle(canvas, (0, 0), (canvas_width - 1, canvas_height - 1), (0, 255, 0), 2) 
                    """for x in range(canvas_width):
                        canvas[0, x, :] = [255, 0, 0]
                        canvas[canvas_height - 1, x, :] = [255, 0, 0]
                    for y in range(canvas_height):
                        canvas[y, 0, :] = [255, 0, 0]
                        canvas[y, canvas_width - 1, :] = [255, 0, 0]"""
                canvasses.append(canvas)
            out_image = cv2.hconcat(canvasses)
            preview_image = cv2.resize(out_image, (600, 400))
            #out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
            
        elif self.print_format == "2x6":
            image_aspect_ratio = image_shape[1] / image_shape[0]
            
            image_width = 600
            image_height = int(image_width / (image_aspect_ratio * self._h_crop) * self._v_crop)
            
            canvas_width = image_width
            canvas_height = image_width * 3
            
            if self.logo is not None:
                logo_width, logo_height, logo_x_offset, logo = self.resize_logo(canvas_width)
                y_padding = int((canvas_height - (image_height * 3) - logo_height) / 5)
            else:
                y_padding = int((canvas_height - (image_height * 3)) / 4)
            
            if y_padding < 0:
                raise ValueError("Image is too tall, try increasing v crop or decreasing h crop")
                
            canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255
            y = y_padding
            for image in images:
                cropped = crop_image(image, x_ratio=self._h_crop, y_ratio=self._v_crop)
                resized = cv2.resize(cropped, (image_width, image_height))
                end_y = y + image_height
                canvas[y : end_y, :, :] = resized
                y += y_padding + image_height
                
            if self.logo is not None:
                end_y = y + logo_height
                if end_y > canvas_height:
                    raise ValueError("Logo is too tall, try decreasing the width scale")
                canvas[y : end_y, logo_x_offset:logo_x_offset + logo_width, :] = logo
                
            preview_image = cv2.resize(canvas, (220, 660), cv2.INTER_NEAREST)
            out_image = cv2.hconcat([canvas, canvas])
            #out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
        
        elif self.print_format == "3x2":
            aspect_ratio = 3/2
        
            cropped_images = []
            y_ratio = (image.shape[1] / aspect_ratio) / image.shape[0]
            cropped_images = [crop_image(image, y_ratio=y_ratio) for image in images]
                
            stacks = []
            for i in range(0, 4, 2):
                stack = cv2.vconcat([cropped_images[i], cropped_images[i + 1]])
                stacks.append(stack)
                
            out_image = cv2.hconcat(stacks)
            preview_image = cv2.resize(out_image, (600, 400))
            out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
            
        if self.h_pad:
            image_height = out_image.shape[0]
            image_width = out_image.shape[1]
            pad_height = int((image_height * self.h_pad) / 2)
            pad = np.ones((pad_height, image_width, 3), dtype=np.uint8) * 255
            out_image = cv2.vconcat([pad, out_image, pad])

        if self.test_mode:
            thickness = 3
            colors = [
                [255, 0, 255],
                [0, 0, 255],
                [0, 255, 255],
                [0, 255, 0],
                [255, 255, 0],
                [255, 0, 0],
                [0, 0, 0],
            ]
            for i, color in enumerate(colors):
                offset = i * thickness * 2
                cv2.rectangle(
                    out_image, 
                    (offset, offset), 
                    (out_image.shape[1] - 1 - offset, out_image.shape[0] - 1 - offset), 
                    color,
                    thickness
                ) 
        return out_image, preview_image
        
    def format_and_save_print(self, image_paths, print_path, preview_path):
        out_image, preview_image = self.format_print(image_paths)
        cv2.imwrite(print_path, out_image)
        cv2.imwrite(preview_path, preview_image)
        
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
    
