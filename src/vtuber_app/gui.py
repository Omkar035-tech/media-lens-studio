import dearpygui.dearpygui as dpg
import numpy as np
from typing import Callable, Optional

class VTuberGUI:
    def __init__(self, 
                 on_import_vrm: Callable[[str], None],
                 on_import_fbx: Callable[[str], None],
                 on_calibrate: Callable[[], None]):
        self.on_import_vrm = on_import_vrm
        self.on_import_fbx = on_import_fbx
        self.on_calibrate = on_calibrate
        
        self.texture_data = np.zeros((360, 640, 4), dtype=np.float32)

    def setup(self):
        dpg.create_context()
        dpg.create_viewport(title='VTuber Python App', width=1024, height=768)
        
        with dpg.texture_registry(show=False):
            dpg.add_dynamic_texture(width=640, height=360, default_value=self.texture_data, tag="preview_texture")

        with dpg.window(label="Main Controls", width=300, height=768, pos=(0, 0), no_move=True, no_close=True):
            dpg.add_text("Model Import")
            dpg.add_button(label="Import VRM", callback=lambda: dpg.show_item("vrm_file_dialog"))
            dpg.add_button(label="Import FBX", callback=lambda: dpg.show_item("fbx_file_dialog"))
            
            dpg.add_separator()
            dpg.add_text("Calibration")
            dpg.add_button(label="Calibrate Neutral Pose", callback=self.on_calibrate)
            
            dpg.add_separator()
            dpg.add_text("Sensitivity")
            dpg.add_slider_float(label="Eye Sensitivity", default_value=1.0, min_value=0.1, max_value=2.0)
            dpg.add_slider_float(label="Mouth Sensitivity", default_value=1.0, min_value=0.1, max_value=2.0)
            dpg.add_slider_float(label="Body Sensitivity", default_value=1.0, min_value=0.1, max_value=2.0)
            
            dpg.add_separator()
            dpg.add_text("Bone Mapping")
            with dpg.collapsing_header(label="Mixamo Mapping"):
                dpg.add_input_text(label="Left Arm", default_value="mixamorig:LeftArm")
                dpg.add_input_text(label="Right Arm", default_value="mixamorig:RightArm")
                dpg.add_input_text(label="Spine", default_value="mixamorig:Spine")

        with dpg.window(label="Live Preview", width=660, height=400, pos=(310, 0), no_close=True):
            dpg.add_image("preview_texture")

        # File Dialogs
        with dpg.file_dialog(directory_selector=False, show=False, callback=self._vrm_callback, id="vrm_file_dialog", width=600, height=400):
            dpg.add_file_extension(".vrm")
            
        with dpg.file_dialog(directory_selector=False, show=False, callback=self._fbx_callback, id="fbx_file_dialog", width=600, height=400):
            dpg.add_file_extension(".fbx")

        dpg.setup_dearpygui()
        dpg.show_viewport()

    def _vrm_callback(self, sender, app_data):
        file_path = app_data['file_path_name']
        self.on_import_vrm(file_path)

    def _fbx_callback(self, sender, app_data):
        file_path = app_data['file_path_name']
        self.on_import_fbx(file_path)

    def update_preview(self, frame_rgba):
        # frame_rgba should be normalized float32 [0, 1]
        dpg.set_value("preview_texture", frame_rgba)

    def render_frame(self):
        dpg.render_dearpygui_frame()

    def is_running(self):
        return dpg.is_dearpygui_running()

    def cleanup(self):
        dpg.destroy_context()
