#  Copyright (c) 2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import time
import portpicker  # type: ignore
from websockets.sync.server import serve, ServerConnection, WebSocketServer
from websockets import ConnectionClosed
from threading import Thread, ThreadError, current_thread
from typing import Optional, Union, Callable
from queue import SimpleQueue, Empty
from http.server import HTTPServer, BaseHTTPRequestHandler
from functools import partial

from .ssv_logging import log


class SSVCanvasStreamServerHTTP(BaseHTTPRequestHandler):
    def __init__(self, msg_queue: SimpleQueue, is_alive: Callable[[], bool], *args, **kwargs):
        self._msg_queue = msg_queue
        self._is_alive = is_alive
        super().__init__(*args, **kwargs)

    def do_GET(self):
        self.send_response(200)
        self.send_header('x-colab-notebook-cache-control', 'no-cache')
        boundary = "videoframeboundary"
        self.send_header("content-type", f"multipart/x-mixed-replace; boundary={boundary}")
        self.send_header("Access-Control-Allow-Origin", "*")
        # self.send_header("content-length", str(12))
        self.end_headers()
        self.wfile.write(f"\r\n--{boundary}\r\n".encode("utf-8"))
        timestamp = 0
        while True or self._is_alive():
            try:
                msg = self._msg_queue.get(block=True, timeout=1)
            except Empty:
                continue
            try:
                self.wfile.write(f"Content-Type: image/jpeg\r\n"
                                 f"Content-Length: {len(msg)}\r\n"
                                 f"X-Timestamp: {timestamp}.0000\r\n"
                                 f"\r\n".encode("utf-8"))
                self.wfile.write(msg)
                self.wfile.write(f"\r\n--{boundary}\r\n".encode("utf-8"))
                timestamp += 1
            except ConnectionError:
                return


class SSVCanvasStreamServer:
    """
    A basic websocket/http server which serves frame data to the SSV canvas.
    """

    def __init__(self, http: bool = False, port: Optional[int] = None, timeout: float = 10):
        self._port = port if port is not None else portpicker.pick_unused_port()
        self._hostname = "localhost"
        self._http = http
        self._server: Optional[Union[HTTPServer, WebSocketServer]] = None
        self._msg_queue: SimpleQueue[bytes] = SimpleQueue()
        self._is_alive = True
        self._heartbeat_time = time.monotonic()
        self._timeout = timeout
        self._server_thread: Thread = Thread(daemon=True, name=f"SSV Canvas Stream Server - {id(self):#08x}",
                                             target=self._run_server)
        self._server_thread.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    @property
    def url(self) -> str:
        """Gets the URL of this websocket."""
        if self._http:
            # noinspection HttpUrlsUsage
            return f"http://{self._hostname}:{self._port}/"
        else:
            return f"ws://{self._hostname}:{self._port}/"

    @property
    def is_alive(self):
        # Check heartbeat
        if self._is_alive and time.monotonic() - self._heartbeat_time < self._timeout:
            return True
        else:
            self._is_alive = False
        return False

    def _run_server(self):
        """
        Starts a new server in a new thread.
        """
        # log(f"Starting streaming server on ws://{self._hostname}:{self._port}/...", severity=logging.INFO)
        if self._http:
            handler = partial(SSVCanvasStreamServerHTTP, self._msg_queue, lambda: self.is_alive)
            with HTTPServer((self._hostname, self._port), handler) as server:
                self._server = server
                self._server.serve_forever()
        else:
            # Disable compression since the video data we're sending is already compressed and DEFLATE is really slow
            with serve(self._on_connect, self._hostname, self._port, compression=None) as server:
                self._server = server
                self._is_alive = True
                server.serve_forever()

    def _on_connect(self, connection: ServerConnection):
        """
        Called when a client connects to the websocket.

        :param connection: the websocket connection object.
        """
        # log(f"Canvas connected to streaming server.", severity=logging.INFO)
        # Empty the queue as soon as the connection is established; the client doesn't want any potentially old frames.
        for i in range(self._msg_queue.qsize()):
            self._msg_queue.get_nowait()
        self._is_alive = True
        while self.is_alive:
            try:
                msg = self._msg_queue.get(block=True, timeout=1)
            except Empty:
                continue
            try:
                connection.send(msg)
            except ConnectionClosed:
                self._is_alive = False
                # log(f"Remote websocket connection closed.", severity=logging.INFO)
                return

    def close(self):
        """
        Shuts down the websocket server.
        """
        if current_thread() == self._server_thread:
            raise ThreadError("Server cannot be closed from its own thread!")
        # log(f"Websocket connection closed.", severity=logging.INFO)
        self._is_alive = False
        self._server.shutdown()

    def send(self, msg: bytes):
        """
        Sends a bytes packet to the websocket.

        :param msg: the packet to send.
        """
        if self._is_alive:
            if self._msg_queue.qsize() > 10:
                log("Streaming server is more than 10 frames behind! Consider reducing bandwidth by increasing "
                    "the stream compression.", severity=logging.WARN)
                # Try and catch up by skipping frames
                for i in range(self._msg_queue.qsize()-1):
                    self._msg_queue.get_nowait()
                return
            self._msg_queue.put_nowait(msg)

    def heartbeat(self):
        """
        Sends a heartbeat to the server to keep it alive.
        """
        self._heartbeat_time = time.monotonic()
