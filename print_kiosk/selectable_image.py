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
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
from kivy.properties import BooleanProperty, StringProperty
from kivy.metrics import dp  # Import dp function
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.config import Config


class SelectableImage(RecycleDataViewBehavior, AsyncImage):
    ''' Add selection support to the Image '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    source = StringProperty()
    color_photo_path = StringProperty()
    gray_photo_path = StringProperty()
    print_source = StringProperty()
    touch_start_pos = [0, 0]

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        self.parent_gallery = rv
        self.apply_selection(data['selected'])
        return super(SelectableImage, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(SelectableImage, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            self.touch_start_pos = touch.pos
            self.apply_selection(not self.selected)
            #return self.parent.select_with_touch(self.index, touch)
            
    def on_touch_up(self, touch): 
        if self.collide_point(*touch.pos) and self.selectable:
            distance = ((touch.pos[0] - self.touch_start_pos[0]) ** 2 + 
                        (touch.pos[1] - self.touch_start_pos[1]) ** 2) ** 0.5
            if distance < dp(10):
                if self.selected and not self.parent_gallery.separate_gray_thumbnails:
                    Clock.schedule_once(self.show_image_popup, 0)
                
    def apply_selection(self, is_selected):
        ''' Respond to the selection of items in the view. '''
        rv = self.parent_gallery
        index = self.index
        if is_selected:
            self.color = [1, 1, 1, 0.1]
            self.parent_gallery.add_print_selection(rv.data[index]["print_source"])
            print("selection added for {0}".format(rv.data[index]["print_source"]))
        else:
            self.color = [1, 1, 1, 1]
            self.parent_gallery.remove_print_selection(rv.data[index]["print_source"])
            print("selection removed for {0}".format(rv.data[index]["print_source"]))
        self.selected = is_selected
        rv.data[index]["selected"] = is_selected
        
    def show_image_popup(self, foo):
        ''' Show a popup with the expanded image '''
        layout = FloatLayout()
        popup = Popup(title='Expanded Image View',
                      content=layout,
                      size_hint=(1, 0.6))
        
        if self.color_photo_path:
            main_source = self.color_photo_path
            if self.gray_photo_path:
                gray_source = self.gray_photo_path
            else:
                gray_source = None
        else:
            main_source = self.gray_photo_path
            gray_source = None
        print("Main source:", main_source, "Gray source:", gray_source)
        
        image = AsyncImage(source=self.source, allow_stretch=True, size_hint=(1, 1), pos_hint={'x': 0, 'y': 0.1})
        layout.add_widget(image)
        
        # Define the close button
        close_button = Button(text='Close', size_hint=(0.1, 0.1),
                              pos_hint={'x': 0.6, 'y': 0})
                              
        close_button.bind(on_release=popup.dismiss)
        layout.add_widget(close_button)
        
        self.print_source = main_source
        
        # Define the toggle button and its callback
        if main_source and gray_source:
            toggle_button = ToggleButton(text='Black & White', size_hint=(0.2, 0.1),
                                         pos_hint={'x': 0.4, 'y': 0})
            layout.add_widget(toggle_button)
            
            def on_toggle(instance):
                print(instance.state)
                if instance.state == 'down':
                    instance.text = 'Color'
                    image.source = gray_source
                    self.print_source = gray_source
                else:
                    instance.text = 'Black & White'
                    image.source = self.source
                    self.print_source = main_source
                print(image.source)
                image.reload()
            
            toggle_button.bind(on_press=on_toggle)
        
        # Define the print button and its callback
        print_button = Button(text='Print', size_hint=(0.1, 0.1),
                              pos_hint={'x': 0.3, 'y': 0})
        layout.add_widget(print_button)
        
        def on_print(instance):
            popup.dismiss()
            Clock.schedule_once(self.show_confirm_print_popup, 0)
        
        print_button.bind(on_release=on_print)
        
        popup.open()

    def show_confirm_print_popup(self, instance):
        layout = FloatLayout()
        popup = Popup(title='Confirm print?',
                      content=layout,
                      size_hint=(0.5, 0.3))
                      
        yes_button = Button(text='Yes', size_hint=(0.5, 1),
                              pos_hint={'x': 0, 'y': 0})
            
        def close_popup(instance):
            popup.dismiss()
                              
        def print_image(instance):
            print("Printing", self.print_source)
            close_popup(instance)
            self.print_image()
            Clock.schedule_once(self.show_printing_popup, 0)
                              
        yes_button.bind(on_release=print_image)
        layout.add_widget(yes_button)
                      
        no_button = Button(text='No', size_hint=(0.5, 1),
                              pos_hint={'x': 0.5, 'y': 0})
        no_button.bind(on_release=close_popup)
        layout.add_widget(no_button)
        
        popup.open()

    def show_printing_popup(self, instance):
        layout = FloatLayout()
        popup = Popup(title='Printing!',
            content=layout,
            size_hint=(0.8, 0.8))
        
        Clock.schedule_once(popup.dismiss, 10)
        
        popup.open()
        
    def print_image(self):
        self.parent_gallery.add_print_selection(self.print_source)
