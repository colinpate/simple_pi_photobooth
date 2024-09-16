from collections import OrderedDict
import numpy as np
import time

class OverlayManager:
    def __init__(self, display_width, display_height):
        self.layers = OrderedDict()
        self.layers["main"] = None
        self.main_layer_exclusive = False
        self.layers_changed = True
        self.display_width = display_width
        self.display_height = display_height
        
    def set_layer(self, layer, name="main", exclusive=False):
        self.layers_changed = True
        if exclusive:
            if not (name == "main"):
                raise ValueError("Only the main layer can be exclusive")
            self.main_layer_exclusive = True
            self.layers["main"] = layer
        else:
            if name == "main":
                self.main_layer_exclusive = False
            self.layers[name] = layer
        
    def update_overlay(self):
        if self.layers_changed:
            start_time = time.time()
            self.layers_changed = False
            if self.main_layer_exclusive:
                overlay = self.layers["main"]
            else:
                if not (self.layers["main"] is not None):
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
                    overlay = self.layers["main"]
                
                for name, layer in self.layers.items():
                    if (layer is not None) and (name != "main"):
                        is_empty = False
                        layer_alpha_1chan = np.array(layer[:,:,3], dtype=np.float32) / 255
                        layer_alpha = np.stack([layer_alpha_1chan]*3, axis=-1)
                        layer_alpha_inv = np.ones(layer_alpha.shape, dtype=np.float32) - layer_alpha
                        layer_rgb = layer[:,:,:3] * layer_alpha
                        overlay[:, :, :3] = (overlay[:,:,:3] * layer_alpha_inv) + layer_rgb
                        # Just add the alphas
                        overlay[:,:,3] = np.clip(overlay[:,:,3] + layer[:,:,3], a_min=0, a_max=255) 
                        
                if is_empty:
                    overlay = None
            time_ms = int((time.time() - start_time)*1000)
            print("Overlay update time", time_ms, "ms")
            return True, overlay
        else:
            return False, None
            
        
    
