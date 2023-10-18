#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import base64
import io
import logging
import sys
import time
from typing import Optional
from io import BytesIO
from multiprocessing import Process, Queue
from queue import Empty

from PIL import Image

from .ssv_render import SSVRender
from .ssv_render_opengl import SSVRenderOpenGL
from . import ssv_logging
from .ssv_logging import log


class SSVRenderProcessLogger(io.StringIO):
    def __init__(self, tx_queue: Queue):
        super().__init__()
        self.tx_queue = tx_queue

    def write(self, text: str) -> int:
        self.tx_queue.put(("LogM", text))
        return len(text)  # super().write(text)


class SSVRenderProcessServer:
    """
    This class listens for render commands and dispatches them to the renderer. This class is intended to be constructed
    in a dedicated process.
    """

    def __init__(self, backend, command_queue_tx, command_queue_rx, log_severity):
        self._renderer: Optional[SSVRender] = None
        self._command_queue_tx: Queue = command_queue_tx
        self._command_queue_rx: Queue = command_queue_rx
        self.__init_logger(log_severity)

        self.running = False
        self.target_framerate = 60
        self.output_size = (640, 480)
        self.stream_mode = "png"

        self.__init_render_process(backend)

    def __init_logger(self, log_severity):
        ssv_logging.set_severity(log_severity)
        log_stream = SSVRenderProcessLogger(self._command_queue_tx)
        ssv_logging.set_output_stream(log_stream, level=log_severity, prefix="pySSV_Render")

    def __init_render_process(self, backend):
        if backend == "opengl":
            self._renderer = SSVRenderOpenGL()
        else:
            self._renderer = None
            log(f"Backend '{backend}' does not exist!", logging.ERROR)

        self.__render_process_loop()

    def __render_process_loop(self):
        last_frame_time = time.time()
        timeout = None
        if self.target_framerate > 0:
            delta_time = 1 / self.target_framerate
        else:
            delta_time = 1

        while True:
            # log(f"Parse command finished, timeout={timeout}, running={self.running}")
            current_time = time.time()
            delta_time = current_time - last_frame_time
            if self.running and (self.target_framerate <= 0 or delta_time >= 1 / self.target_framerate):
                self.__render_frame()
                last_frame_time = current_time

            if self.running and self.target_framerate > 0:
                timeout = max(1 / self.target_framerate - delta_time, 0)
            else:
                timeout = None
            self.__parse_render_command(timeout)
            if self._command_queue_rx.qsize() > 1:
                # If the command queue is getting backed (due to poor framerate for instance) prioritise that so that
                # user control is not delayed.
                for i in range(self._command_queue_rx.qsize()):
                    self.__parse_render_command(0)

    def __parse_render_command(self, timeout):
        try:
            command, *command_args = self._command_queue_rx.get(block=True, timeout=timeout)
            log(f"Render Process: Received command '{command}': {command_args}", severity=logging.DEBUG)
        except Empty:
            command = None
            command_args = None

        if command is None:
            # Command is None if we timeout before receiving a new command, this isn't an error in this case.
            pass
        elif command == "Stop":
            return False
        elif command == "UFBO":
            # New/Update frame buffer
            self._renderer.update_frame_buffer(*command_args)
            if command_args[0] == 0:
                self.output_size = command_args[1]
        elif command == "DFBO":
            # Delete frame buffer
            self._renderer.delete_frame_buffer(command_args[0])
        elif command == "Rndr":
            # Start rendering at a given framerate
            self.target_framerate = command_args[0]
            self.stream_mode = command_args[1]
            self.running = self.target_framerate != 0
        elif command == "UpdU":
            # Update uniform
            self._renderer.update_uniform(*command_args)
        elif command == "UpdV":
            # Update buffer
            self._renderer.update_vertex_buffer(*command_args)
        elif command == "RegS":
            # Register shader
            self._renderer.register_shader(*command_args)
        elif command == "LogC":
            # Log Context Info
            self._renderer.log_context_info(command_args[0])
        elif command == "DbRT":
            # Debug Render Test
            if isinstance(self._renderer, SSVRenderOpenGL):
                self._renderer.dbg_render_test()
        else:
            log(f"Render process received unknown command from client '{command}' with args: {command_args}",
                severity=logging.ERROR)
            return False

        return True

    def __render_frame(self):
        if not self._renderer.render():
            self.running = False
        if self.stream_mode == "png":
            stream_data = self.__to_png(self._renderer.get_frame())
        elif self.stream_mode == "jpg":
            stream_data = self.__to_jpg(self._renderer.get_frame(3))
        else:
            stream_data = None
        self._command_queue_tx.put(("NFrm", stream_data))

    def __to_png(self, frame):
        image = Image.frombytes('RGBA', self.output_size, frame)
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        image_bytes = BytesIO()
        image.save(image_bytes, format='png')
        return "data:image/png;base64,{}".format(base64.b64encode(image_bytes.getvalue()).decode('ascii'))

    def __to_jpg(self, frame):
        image = Image.frombytes('RGB', self.output_size, frame)
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        image_bytes = BytesIO()
        image.save(image_bytes, format='jpeg')
        return "data:image/jpg;base64,{}".format(base64.b64encode(image_bytes.getvalue()).decode('ascii'))
