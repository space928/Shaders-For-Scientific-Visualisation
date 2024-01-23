#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import base64
import io
import logging
import sys
import time
from typing import Optional
from io import BytesIO
from multiprocessing import Process, Queue, current_process
from threading import current_thread
from queue import Empty
import enum

import numpy as np
from PIL import Image
import av

from .ssv_render import SSVRender
from .ssv_render_opengl import SSVRenderOpenGL
from . import ssv_logging
from .ssv_logging import log, SSVLogStream


class SSVStreamingMode(enum.Enum):
    """
    Represents an image/video streaming mode for pySSV. Note that some of these streaming formats may not be
    supported on all platforms.
    """
    JPG = "jpg"
    PNG = "png"

    VP8 = "vp8"
    VP9 = "vp9"
    H264 = "h264"
    HEVC = "hevc"
    """Not supported"""
    MPEG4 = "mpeg4"
    """Not supported"""

    MJPEG = "mjpeg"


class SSVRenderProcessLogger(SSVLogStream):
    """
    A StringIO pipe for sending log messages to, this class pipes incoming messages to "LogM" commands.
    """
    def __init__(self, tx_queue: Queue):
        super().__init__()
        self.tx_queue = tx_queue

    def write(self, text: str, severity: int = logging.INFO+1) -> int:
        self.tx_queue.put(("LogM", severity, text))
        return len(text)  # super().write(text)


class SSVRenderProcessServer:
    """
    This class listens for render commands and dispatches them to the renderer. This class is intended to be constructed
    in a dedicated process by SSVRenderProcessClient.
    """

    def __init__(self, backend: str, command_queue_tx: Queue, command_queue_rx: Queue, log_severity: int,
                 timeout: Optional[float], use_renderdoc_api: bool = False):
        self._renderer: Optional[SSVRender] = None
        self._command_queue_tx: Queue = command_queue_tx
        self._command_queue_rx: Queue = command_queue_rx
        self.__init_logger(log_severity)
        self._use_renderdoc_api = use_renderdoc_api
        # Makes it easier to find the render thread in the profiler
        current_thread().name = current_process().name

        self.running = False
        self.target_framerate = 60
        self.output_size = (640, 480)
        self.stream_mode: SSVStreamingMode = SSVStreamingMode.PNG
        self.watchdog_time = timeout
        self.encode_quality: Optional[float] = None
        self.log_frame_timing = False

        self._last_heartbeat_time = 0
        self._frame_buffer_bytes = bytearray()
        # self._dbg_command_stats = {}
        self._video_stream: Optional[av.video.VideoStream] = None
        self._video_container: Optional[av.container.OutputContainer] = None

        # Frame time stats for debugging
        self.avg_delta_time = 1/self.target_framerate
        self.max_delta_time = 1/self.target_framerate
        self.avg_delta_time_encode = 1 / self.target_framerate
        self.max_delta_time_encode = 1 / self.target_framerate

        self.__init_video_encoder()
        self.__init_render_process(backend)

    _supported_video_formats: set[str] = {
        SSVStreamingMode.H264,
        SSVStreamingMode.HEVC,
        SSVStreamingMode.VP8,
        SSVStreamingMode.VP9,
        SSVStreamingMode.MPEG4,
        SSVStreamingMode.MJPEG
    }

    # This dict stores the bit rate/quality factor that a stream quality of '100' should equal
    _streaming_format_quality_scaling: dict[str, int] = {
        SSVStreamingMode.JPG: 100,
        SSVStreamingMode.PNG: 7,
        SSVStreamingMode.VP8: 3500000,
        SSVStreamingMode.VP9: 3500000,
        SSVStreamingMode.H264: 40000000,
        SSVStreamingMode.HEVC: 40000000,
        SSVStreamingMode.MPEG4: 40000000,
        SSVStreamingMode.MJPEG: 68,
    }

    def __init_video_encoder(self):
        """
        Initialises or reinitialises the video encoder using the given stream_mode.
        """
        if self.stream_mode not in self._supported_video_formats:
            return

        class FakeIO(io.RawIOBase):
            name: str = "stream.mkv"

            def writable(self) -> bool:
                return True

            def readable(self) -> bool:
                return False

            def write(self, __b: bytes) -> Optional[int]:
                # print(f"Writing: {len(__b)} bytes...")
                return len(__b)

        if self._video_container is not None:
            self._video_container.close()

        # Setting format to "null" here effectively disables muxing
        self._video_container = av.open(FakeIO(), mode="w", format="null")
        # self._video_container.flags |= self._video_container.flags.FLUSH_PACKETS

        stream = self._video_container.add_stream(self.stream_mode.value, rate=self.target_framerate)
        stream.width = self.output_size[0]
        stream.height = self.output_size[1]
        stream.pix_fmt = "yuv420p"
        stream.options = {
            # Set some options to reduce latency as much as possible, depending on the codec these can can have a
            # large impact on the output size.
            "g": "30",
            "lag-in-frames": "2",
            "speed": "10",
            "quality": "realtime",
        }
        if self.stream_mode == SSVStreamingMode.H264:
            stream.options["g"] = "1"
            stream.options["zerolatency"] = "1"
            stream.options["tune"] = "zerolatency"
            stream.options["preset"] = "fast"
        elif self.stream_mode == SSVStreamingMode.MJPEG:
            stream.options["strict_std_compliance"] = "unofficial"
            stream.options["color_range"] = "2"
            stream.options["qscale"] = "0"
            stream.options["huffman"] = "optimal"
            # Creates a warning message, but seems to be the only way to get full range jpeg encoding...
            stream.pix_fmt = "yuvj420p"
        if self.encode_quality is not None:
            if self.stream_mode == SSVStreamingMode.MJPEG:
                # MJPEG doesn't seem to respect CBR
                q = min(max(round(
                    (1-(self.encode_quality/100)) * self._streaming_format_quality_scaling[self.stream_mode])+1, 1), 69)
                stream.options["qmin"] = str(q)
                stream.options["qmax"] = str(q)
                if self.encode_quality >= 90:
                    stream.pix_fmt = "yuvj444p"
            else:
                q = max(round(self.encode_quality/100 * self._streaming_format_quality_scaling[self.stream_mode]), 10)
                stream.options["b"] = str(q)
                if self.encode_quality >= 90 and self.stream_mode in {SSVStreamingMode.HEVC, SSVStreamingMode.VP9}:
                    stream.pix_fmt = "yuv444p"
        self._video_stream = stream

    def __init_logger(self, log_severity: int):
        ssv_logging.set_severity(log_severity)
        log_stream = SSVRenderProcessLogger(self._command_queue_tx)
        ssv_logging.set_output_stream(log_stream, level=log_severity, prefix="pySSV_Render")

    def __init_render_process(self, backend: str):
        """
        Creates a new renderer for the given backend and starts the render process loop.

        :param backend: the render backend to use.
        """
        if backend == "opengl":
            self._renderer = SSVRenderOpenGL(self._use_renderdoc_api)
        else:
            self._renderer = None
            log(f"Backend '{backend}' does not exist!", logging.ERROR)

        self.__render_process_loop()

    def __render_process_loop(self):
        """
        Runs the main render process loop. This function continuously checks for new render commands and
        dispatches render frame commands as needed.
        """
        last_frame_time = time.perf_counter()
        timeout = 0

        self._last_heartbeat_time = time.monotonic()

        frame = 0
        while True:
            # Check heartbeat
            if self.watchdog_time is not None and (time.monotonic() - self._last_heartbeat_time) > self.watchdog_time:
                self.__shutdown("watchdog")
                return

            # Render the next frame if it's time to
            delta_time = time.perf_counter() - last_frame_time
            if self.running and (self.target_framerate <= 0 or delta_time >= 1 / self.target_framerate):
                last_frame_time = time.perf_counter()
                self.__render_frame()

                # Frame time stats
                if self.log_frame_timing:
                    frame += 1
                    if frame % self.target_framerate == 0:
                        log(f"Render time: Avg={self.avg_delta_time*1000:.2f} ms "
                            f"Max={self.max_delta_time*1000:.2f} ms \t// "
                            f"Encode time Avg={self.avg_delta_time_encode*1000:.2f} ms "
                            f"Max={self.max_delta_time_encode*1000:.2f} ms   \t// "
                            f"asleep={timeout*1000:.2f} ms \t// "
                            f"FPS: Avg={1/(self.avg_delta_time+self.avg_delta_time_encode):.1f} "
                            f"Avg+Sync={1/(self.avg_delta_time+self.avg_delta_time_encode+timeout):.1f} "
                            f"Min={1/(self.max_delta_time+self.max_delta_time_encode):.1f}", severity=logging.INFO)
                        self.max_delta_time = 0
                        self.max_delta_time_encode = 0

            # Execute any render commands that are waiting for us
            if self._command_queue_rx.qsize() > 0:
                size = self._command_queue_rx.qsize()
                # if size > 32:
                #     log(f"Render process is struggling to keep up! Command queue size>32 (={size})",
                #         severity=logging.WARN)
                # If the command queue is getting backed up (due to poor framerate for instance) prioritize that so that
                # user control is not delayed.
                for i in range(size):
                    if not self.__parse_render_command(0):
                        self.__shutdown("requested by client")
                        return
            else:
                # Work out how long the command processor can block for
                delta_time = time.perf_counter() - last_frame_time
                if self.running and self.target_framerate > 0:
                    timeout = max(1 / self.target_framerate - delta_time, 0) * 0.5
                else:
                    # If this timeout is infinite then the watchdog can't kill paused render processes which also need
                    # to be killed otherwise all the RenderDoc sockets get used up...
                    if self.watchdog_time is None:
                        timeout = 5
                    else:
                        timeout = min(self.watchdog_time*0.5, 1)

                # Wait for <timeout and (potentially) execute one render command
                # if not self.__parse_render_command(timeout):
                #     self.__shutdown("requested by client")
                #     return
                # Because Queue.get() uses time.monotonic() internally, it doesn't have the required timeout precision
                # for our use case.
                time.sleep(timeout)

    def __send_async_result(self, query_id: int, *args):
        """
        Sends the result of a query command back to the client.

        :param query_id: the query id from the client associated with this query.
        :param args: the result to send back to the client.
        """
        # Send an async result back to the client with the client's request id
        self._command_queue_tx.put(("ARes", query_id, *args))

    def __parse_render_command(self, timeout: Optional[float]) -> bool:
        """
        Parses and executes the next render command. Blocks for up to ``timeout`` seconds to wait for the command
        queue to fill up.

        :param timeout: the maximum amount of time to wait for a new message in seconds before giving up. Pass ``None``
                        to wait indefinitely.
        :return: ``False`` if the render process should exit.
        """
        try:
            command, *command_args = self._command_queue_rx.get(block=(timeout is None or timeout != 0),
                                                                timeout=timeout)
            # log(f"Render Process: Received command '{command}': {command_args}", severity=logging.INFO)
        except Empty:
            return True
        except KeyboardInterrupt or ValueError:
            log(f"Render process shutting down because client died unexpectedly.", severity=logging.INFO)
            return False

        # DBG
        # _command = command
        # if _command is None:
        #     _command = "NnBlk" if timeout != 0 else "Nn000"
        # if _command in self._dbg_command_stats:
        #     self._dbg_command_stats[_command] += 1
        # else:
        #     self._dbg_command_stats[_command] = 1

        if command is None:
            # Command is None if we time out before receiving a new command, this isn't an error in this case.
            pass
        elif command == "Stop":
            return False
        elif command == "HrtB":
            self._last_heartbeat_time = time.monotonic()
        elif command == "SWdg":
            self.watchdog_time = command_args[0]
        elif command == "UFBO":
            # New/Update frame buffer
            self._renderer.update_frame_buffer(*command_args)
            if command_args[0] == 0:
                self.output_size = command_args[2]
        elif command == "DFBO":
            # Delete frame buffer
            self._renderer.delete_frame_buffer(command_args[0])
        elif command == "Rndr":
            # A render command needs to count as the first heartbeat so that the watchdog doesn't kill us immediately
            self._last_heartbeat_time = time.monotonic()
            # Start rendering at a given framerate
            self.target_framerate = command_args[0]
            self.stream_mode = SSVStreamingMode(command_args[1])
            self.encode_quality = command_args[2]
            self.__init_video_encoder()
            self.running = self.target_framerate != 0
        elif command == "UpdU":
            # Update uniform
            self._renderer.update_uniform(*command_args)
        elif command == "UpdV":
            # Update vertex buffer
            self._renderer.update_vertex_buffer(*command_args)
        elif command == "UpdT":
            # Update texture
            self._renderer.update_texture(*command_args)
        elif command == "UpdS":
            # Update texture sampler
            self._renderer.update_texture_sampler(*command_args)
        elif command == "DelT":
            # Delete texture
            self._renderer.delete_texture(*command_args)
        elif command == "RegS":
            # Register shader
            self._renderer.register_shader(*command_args)
        elif command == "RdCp":
            # Renderdoc capture frame
            self._renderer.renderdoc_capture_frame(*command_args)
        elif command == "LogC":
            # Log Context Info
            self._renderer.log_context_info(command_args[0])
        elif command == "LogT":
            # Log frame Times
            self.log_frame_timing = command_args[0]
        elif command == "GtCt":
            # Get Context info
            ctx = self._renderer.get_context_info()
            self.__send_async_result(command_args[0], ctx)
        elif command == "GtFt":
            # Get average Frame-times
            self.__send_async_result(command_args[0],
                                     self.avg_delta_time, self.max_delta_time,
                                     self.avg_delta_time_encode, self.max_delta_time_encode)
            self.max_delta_time = 0
            self.max_delta_time_encode = 0
        elif command == "GtEx":
            # Get supported extensions
            ext = self._renderer.get_supported_extensions()
            self.__send_async_result(command_args[0], ext)
        elif command == "DbRT":
            # Debug Render Test
            pass
        else:
            log(f"Render process received unknown command from client '{command}' with args: {command_args}",
                severity=logging.ERROR)
            return False

        return True

    def __shutdown(self, reason: str):
        """
        Informs the client that this render process is shutting down.

        :param reason: a string describing why this process is shutting down.
        """
        log(f"Render process shutting down... ({reason})", severity=logging.WARN)
        if self._video_container is not None:
            self._video_container.close()
        self._command_queue_tx.put(("Stop",))

    def __render_frame(self):
        """
        Asks the renderer to render the next frame and sends the new frame back to the client.
        """
        start_time = time.perf_counter()
        render_time = start_time
        if not self._renderer.render():
            self.running = False
        if self.stream_mode == SSVStreamingMode.PNG:
            if len(self._frame_buffer_bytes) == self.output_size[0]*self.output_size[1] * 4:
                self._renderer.read_frame_into(self._frame_buffer_bytes)
            else:
                self._frame_buffer_bytes = bytearray(self._renderer.read_frame())
            render_time = time.perf_counter()
            stream_data = self.__to_png(self._frame_buffer_bytes)
        elif self.stream_mode == SSVStreamingMode.JPG:
            if len(self._frame_buffer_bytes) == self.output_size[0] * self.output_size[1] * 3:
                self._renderer.read_frame_into(self._frame_buffer_bytes, 3)
            else:
                self._frame_buffer_bytes = bytearray(self._renderer.read_frame(3))
            render_time = time.perf_counter()
            stream_data = self.__to_jpg(self._frame_buffer_bytes)
        elif self.stream_mode in self._supported_video_formats:
            if len(self._frame_buffer_bytes) == self.output_size[0] * self.output_size[1] * 3:
                self._renderer.read_frame_into(self._frame_buffer_bytes, 3)
            else:
                self._frame_buffer_bytes = bytearray(self._renderer.read_frame(3))
            render_time = time.perf_counter()
            stream_data = self.__encode_video_frame(self._frame_buffer_bytes)
        else:
            stream_data = None
        # if self.log_frame_timing:
        encode_time = time.perf_counter()
        self.max_delta_time = max(self.max_delta_time, render_time - start_time)
        self.max_delta_time_encode = max(self.max_delta_time_encode, encode_time - render_time)
        self.avg_delta_time = self.avg_delta_time * 0.9 + (render_time - start_time) * 0.1
        self.avg_delta_time_encode = self.avg_delta_time_encode * 0.9 + (encode_time - render_time) * 0.1
        self._command_queue_tx.put(("NFrm", stream_data))

    def __to_png(self, frame: bytearray) -> bytes:
        """
        Converts a framebuffer into a base64 encoded png data url.

        :param frame: the frame as an RGBA8888 buffer of bytes.
        :return: a data url string containing the frame.
        """
        image = Image.frombytes('RGBA', self.output_size, frame)
        # image = image.transpose(Image.FLIP_TOP_BOTTOM)
        image_bytes = BytesIO()
        quality = 5
        if self.encode_quality is not None:
            quality = min(max(round(
                self.encode_quality / 100 * self._streaming_format_quality_scaling[self.stream_mode]), 0), 7)
        image.save(image_bytes, format='png', optimize=False, compress_level=quality)
        return b"data:image/png;base64," + base64.b64encode(image_bytes.getvalue())

    def __to_jpg(self, frame: bytearray) -> bytes:
        """
        Converts a framebuffer into a base64 encoded jpeg data url.

        :param frame: the frame as an RGB888 buffer of bytes.
        :return: a data url string containing the frame.
        """
        image = Image.frombytes('RGB', self.output_size, frame)
        # image = image.transpose(Image.FLIP_TOP_BOTTOM)
        image_bytes = BytesIO()
        quality = 75
        if self.encode_quality is not None:
            quality = min(max(round(
                self.encode_quality / 100 * self._streaming_format_quality_scaling[self.stream_mode]), 0), 100)
        image.save(image_bytes, format='jpeg', quality=quality)
        return b"data:image/jpg;base64," + base64.b64encode(image_bytes.getvalue())

    def __encode_video_frame(self, frame: bytearray) -> bytes:
        """
        Encodes a frame using the initialized video encoder and returns the produced video packet.

        Note that this method provides raw, un-muxed video stream data. If the codec used buffers frames internally
        then this method may return an empty bytes, and the bytes returned may not necessarily be for the current frame.

        :param frame: the frame as an RGB888 buffer of bytes.
        :return: the encoded frame as bytes.
        """
        if self._video_stream is None:
            raise Exception("Video encoder has not been initialised yet!")

        # img = Image.frombytes("RGB", self.output_size, frame)
        # av_frame = av.VideoFrame.from_image(img)
        frame = np.array(frame, copy=False, dtype=np.uint8)
        frame = frame.reshape((self.output_size[1], self.output_size[0], 3))
        av_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
        packets = self._video_stream.encode(av_frame)
        if len(packets) == 1:
            return bytes(packets[0])
        elif len(packets) > 1:
            return b"".join([bytes(p) for p in packets])
        else:
            # raise ValueError(f"Video encoder produced didn't produce any packets for the given frame. Frame might "
            #                  f"have been buffered.")
            return b""
