#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import base64
from io import BytesIO
import logging
import threading
import time

from PIL import Image

from .ssv_render import SSVRender
from .ssv_render_opengl import SSVRenderOpenGL
from .ssv_render_widget import SSVRenderWidget
from .ssv_logging import log


class SSVCanvas:
    """
    An SSV canvas manages the OpenGL rendering context, shaders, and the jupyter widget
    """
    def __init__(self, size, backend="opengl", standalone=False):
        if size is None:
            size = (640, 480)
        self.size = size
        self.standalone = standalone
        self.target_framerate = 60
        if backend == "opengl":
            self.renderer = SSVRenderOpenGL(size)
        else:
            self.renderer = None
            log(f"Backend '{backend}' does not exist!", logging.ERROR)
        if not standalone:
            self.widget = SSVRenderWidget()

    def __to_png(self, frame):
        image = Image.frombytes('RGBA', self.size, frame)
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        image_bytes = BytesIO()
        image.save(image_bytes, format='png')
        return "data:image/png;base64,{}".format(base64.b64encode(image_bytes.getvalue()).decode('ascii'))

    def render_loop(self, exit_flag):
        self.widget.streaming_mode = "png"
        last_frame_time = time.time()
        timeout = 0
        delta_time = 1/self.target_framerate
        while not exit_flag.wait(timeout=timeout):
            self.renderer.dbg_render_test()
            frame = self.renderer.get_frame()
            png = self.__to_png(frame)
            self.widget.stream_data = png

            current_time = time.time()
            delta_time = current_time - last_frame_time
            timeout = max(1/self.target_framerate - delta_time, 0)
            last_frame_time = current_time
            break

    def run(self):
        exit_flag = threading.Event()
        thread = threading.Thread(target=self.render_loop, args=(exit_flag,))

        if not self.standalone:
            from IPython.display import display
            display(self.widget)
            self.widget.observe(lambda x: self.render_loop(exit_flag), names="frame_no")  # names=["mouse_pos_x", "mouse_pos_y"])

        # thread.start()
        self.render_loop(exit_flag)

    def dbg_get_widget(self):
        return self.widget

    def dbg_log_context(self, full=False):
        self.renderer.log_context_info(full=full)
