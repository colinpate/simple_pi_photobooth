import cv2
import numpy as np

class ApplyWatermark:
    def __init__(self, watermark_path, watermark_position="lr", weight=1, h_size=0, offset_x=0, offset_y=0):
        watermark_in = cv2.imread(watermark_path, cv2.IMREAD_UNCHANGED)
        if h_size == 0:
            watermark = watermark_in
        else:
            v_size = (h_size / watermark_in.shape[1]) * watermark_in.shape[0]
            watermark = cv2.resize(watermark_in, dsize=(int(h_size), int(v_size)))
            
        print("apply_watermark.py: Loaded", watermark_path, ", Shape:", watermark.shape)
        
        watermark_alpha_1chan = np.array(watermark[:,:,3], dtype=np.float32) / 255 * weight
        watermark_alpha = np.stack([watermark_alpha_1chan]*3, axis=-1)
        self.watermark_alpha_inv = np.ones(watermark_alpha.shape, dtype=np.float32) - watermark_alpha
        self.watermark_alphad = watermark[:,:,:3] * watermark_alpha
        
        self.watermark_position = watermark_position
        self.offset_x = offset_x
        self.offset_y = offset_y

    def apply_watermark(self, in_image):
        watermark_dims = self.watermark_alphad.shape
        if self.watermark_position[0] == "l": # lower
            start_y = in_image.shape[1] - watermark_dims[1] - self.offset_y
        elif self.watermark_position[0] == "u": # upper
            start_y = self.offset_y
        else:
            raise ValueError("Watermark position must be lr, ur, ll, or ul")
            
        if self.watermark_position[1] == "l": # left
            start_x = self.offset_x
        elif self.watermark_position[1] == "r": # right
            start_x = in_image.shape[0] - watermark_dims[0] - self.offset_x
        else:
            raise ValueError("Watermark position must be lr, ur, ll, or ul")
            
        end_x = start_x + watermark_dims[0]
        end_y = start_y + watermark_dims[1]
        
        in_image_float = np.array(in_image[start_x:end_x,start_y:end_y,:3], dtype=np.float32)
        in_image_float *= self.watermark_alpha_inv
        in_image[start_x:end_x, start_y:end_y,:3] = in_image_float + self.watermark_alphad\
                
    
if __name__ == "__main__":
    #in_image = cv2.imread("../photobooth_site/240713_163044_color.jpg")
    in_image = cv2.imread("../booth_photos/240720_150954_color.jpg")

    print(in_image.shape)
    #watermark = cv2.imread("../photobooth_site/watermarks/doug_anne_watermark.png", cv2.IMREAD_UNCHANGED)
    #watermark = cv2.imread("../photobooth_site/watermarks/small_watermark.png", cv2.IMREAD_UNCHANGED)
    #watermark = cv2.imread("../photobooth_site/watermarks/larger_aquafest_logo.png", cv2.IMREAD_UNCHANGED)
    watermark_path = "../photobooth_site/watermarks/larger_aquafest_logo.png"

    watermarker = ApplyWatermark(
        watermark_path=watermark_path,
        weight=1,
        h_scale=0.25, 
        offset_x=100, 
        offset_y=90
        )
        
    watermarker.apply_watermark(in_image)

    cv2.imwrite("watermarked.jpg", in_image)
    
