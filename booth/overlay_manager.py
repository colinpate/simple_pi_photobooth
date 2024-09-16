from collections import OrderedDict
import numpy as np
import time

class Layer:
    def __init__(self, image):
        self.raw_image = image
        self._active = False
        alpha_1chan = np.array(image[:,:,3], dtype=np.float32) / 255
        alpha = np.stack([alpha_1chan]*3, axis=-1)
        self.alpha_inv = np.ones(alpha.shape, dtype=np.float32) - alpha
        self.rgb = image[:,:,:3] * alpha
        self.alpha = image[:,:,3]
        
    def composite(self, image):
        image[:, :, :3] = (image[:,:,:3] * self.alpha_inv) + self.rgb
        # Just add the alphas
        image[:,:,3] = np.clip(image[:,:,3] + self.alpha, a_min=0, a_max=255) 
        
    def is_active(self):
        return self._active
        
    def activate(self):
        self._active = True
        
    def deactivate(self):
        self._active = False
        

class OverlayManager:
    def __init__(self, display_width, display_height):
        self.layers = OrderedDict()
        self.main_image = None
        self.main_image_exclusive = False
        self.layers_changed = True
        self.display_width = display_width
        self.display_height = display_height
        
    def set_layer(self, image, name):
        self.layers[name] = Layer(image)
        
    def activate_layer(self, name):
        self.layers_changed = True
        self.layers[name].activate()
        
    def deactivate_layer(self, name):
        self.layers_changed = True
        self.layers[name].deactivate()
        
    def set_main_image(self, image, exclusive):
        self.layers_changed = True
        self.main_image = image
        self.main_image_exclusive = exclusive
        
    def update_overlay(self):
        if self.layers_changed:
            start_time = time.time()
            self.layers_changed = False
            if self.main_image_exclusive:
                overlay = self.main_image
            else:
                if self.main_image is None:
                    is_empty = True
                    overlay = np.zeros(
                            (
                                self.display_height,
                                self.display_width,
                                4
                            ), 
                            dtype=np.uint8
                        )
                else:
                    is_empty = False
                    overlay = self.main_image
                
                for name, layer in self.layers.items():
                    if layer.is_active():
                        is_empty = False
                        layer.composite(overlay)
                        
                if is_empty:
                    overlay = None
            time_ms = int((time.time() - start_time)*1000)
            print("Overlay update time", time_ms, "ms")
            return True, overlay
        else:
            return False, None
            
        
    
