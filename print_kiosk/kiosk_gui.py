import kivy
from kivy.app import App
from kivy.uix.image import AsyncImage
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.properties import BooleanProperty, StringProperty
from kivy.metrics import dp  # Import dp function
from kivy.lang import Builder
from glob import glob


from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton

Builder.load_string(
'''
<ImageGallery>:
    viewclass: 'SelectableImage'
    RecycleGridLayout:
        cols: 2
        default_size: None, 400
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
'''
)

class SelectableImage(RecycleDataViewBehavior, AsyncImage):
    ''' Add selection support to the Image '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    source = StringProperty()

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super(SelectableImage, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if self.collide_point(*touch.pos) and self.selectable:
            self.touch_start_pos = touch.pos
            #return self.parent.select_with_touch(self.index, touch)
            
    def on_touch_up(self, touch): 
        if self.collide_point(*touch.pos) and self.selectable:
            distance = ((touch.pos[0] - self.touch_start_pos[0]) ** 2 + 
                        (touch.pos[1] - self.touch_start_pos[1]) ** 2) ** 0.5
            if distance < dp(10):
                self.show_image_popup(self.source)
                
    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        if is_selected:
            print("selection changed to {0}".format(rv.data[index]))
        else:
            print("selection removed for {0}".format(rv.data[index]))
            
    def show_image_popup(self, source):
        ''' Show a popup with the expanded image '''
        layout = FloatLayout()
        popup = Popup(title='Expanded Image View',
                      content=layout,
                      size_hint=(0.8, 0.8))
        
        image_base = source.split("_thumb")[0]
        if image_base.endswith("_gray"):
            image_base = image_base[:-5]
        color_source = image_base + ".jpg"
        gray_source = image_base + "_gray.jpg"
        
        image = AsyncImage(source=color_source, allow_stretch=True, size_hint=(0.8, 0.8), pos_hint={'x': 0.1, 'y': 0.2})
        layout.add_widget(image)
        
        # Define the close button
        close_button = Button(text='Close', size_hint=(0.1, 0.1),
                              pos_hint={'x': 0.6, 'y': 0})
        close_button.bind(on_release=popup.dismiss)
        layout.add_widget(close_button)
        
        # Define the toggle button and its callback
        toggle_button = ToggleButton(text='Black & White', size_hint=(0.2, 0.1),
                                     pos_hint={'x': 0.4, 'y': 0})
        layout.add_widget(toggle_button)
        
        def on_toggle(instance):
            print(instance.state)
            if instance.state == 'down':
                instance.text = 'Color'
                image.source = gray_source
            else:
                instance.text = 'Black & White'
                image.source = color_source
            image.reload()
        
        toggle_button.bind(on_press=on_toggle)
        
        # Define the print button and its callback
        print_button = Button(text='Print', size_hint=(0.1, 0.1),
                              pos_hint={'x': 0.3, 'y': 0})
        layout.add_widget(print_button)
        
        def on_print(instance):
            popup.dismiss()
            self.show_confirm_print_popup(source)
        
        print_button.bind(on_release=on_print)
        
        popup.open()

    def show_confirm_print_popup(self, source):
        layout = FloatLayout()
        popup = Popup(title='Confirm print?',
                      content=layout,
                      size_hint=(0.5, 0.3))
                      
        yes_button = Button(text='Yes', size_hint=(0.5, 1),
                              pos_hint={'x': 0, 'y': 0})
        yes_button.bind(on_release=popup.dismiss)
        layout.add_widget(yes_button)
                      
        no_button = Button(text='No', size_hint=(0.5, 1),
                              pos_hint={'x': 0.5, 'y': 0})
        no_button.bind(on_release=popup.dismiss)
        layout.add_widget(no_button)
        
        popup.open()
        

class ImageGallery(RecycleView):
    def __init__(self, **kwargs):
        super(ImageGallery, self).__init__(**kwargs)
        self.image_dir = "../../party_photos/becca_party_4_13_24/booth_photos/color/"
        
        #self.image_dir = "../../party_photos/Mead_5th_Grade/"
        self.image_paths = glob(self.image_dir + "*.png")
        
        self.data = [{'source': i} for i in self.image_paths]  # Replace with your image paths
        print(self.data)
        print("Layout manager added to the RecycleView.")

class ImageGalleryApp(App):
    def build(self):
        gallery = ImageGallery()
        gallery.scroll_type = ['content', 'bars']
        gallery.bar_width = '30dp'
        print("ImageGallery instance created and configured.")
        return gallery

if __name__ == '__main__':
    ImageGalleryApp().run()
