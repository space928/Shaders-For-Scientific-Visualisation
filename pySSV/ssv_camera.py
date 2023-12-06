#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import typing
from enum import Enum
import numpy as np
import numpy.typing as npt
import math

from .ssv_logging import log


class MoveDir(Enum):
    FORWARD = 0
    BACKWARD = 1
    LEFT = 2
    RIGHT = 3
    UP = 4
    DOWN = 5


class SSVCamera:
    """
    A simple class representing a camera.
    """

    def __init__(self):
        self.position = np.array([0., 0., 0.])
        self.direction = np.array([0., 0., -1.])
        self.fov = 60
        self.clip_dist = [0.1, 1000.0]
        self.move_speed = 0.1
        self.rotate_speed = 0.005
        self.aspect_ratio = 1

        self._mouse_old_pos = np.array([0., 0.])
        self._rotation = np.array([math.pi, 0.])
        self._mouse_was_pressed = False
        self._view_matrix = np.identity(4)
        self._projection_matrix = np.identity(4)
        self._up_vec = np.array([0., 1., 0.])

    def mouse_change(self, mouse_pos: typing.List, mouse_down: bool):
        if mouse_down:
            if not self._mouse_was_pressed:
                self._mouse_was_pressed = True
                self._mouse_old_pos[:] = mouse_pos
            else:
                self._rotation += (np.array(mouse_pos) - self._mouse_old_pos) * self.rotate_speed
                self._rotation[1] = min(max(self._rotation[1], -math.pi/2), math.pi/2)
                self.direction[0] = math.sin(self._rotation[0]) * math.cos(self._rotation[1])
                self.direction[1] = math.sin(self._rotation[1])
                self.direction[2] = math.cos(self._rotation[0]) * math.cos(self._rotation[1])
                self._mouse_old_pos[:] = mouse_pos
        else:
            self._mouse_was_pressed = False

    def move(self, direction: MoveDir):
        if direction == MoveDir.UP:
            self.position[1] += self.move_speed
        elif direction == MoveDir.DOWN:
            self.position[1] -= self.move_speed
        elif direction == MoveDir.RIGHT:
            self.position[0] += self.move_speed
        elif direction == MoveDir.LEFT:
            self.position[0] -= self.move_speed
        elif direction == MoveDir.FORWARD:
            self.position[2] += self.move_speed
        elif direction == MoveDir.BACKWARD:
            self.position[2] -= self.move_speed
        # log(f"Moved position: {self.position}", severity=logging.INFO)

    @property
    def view_matrix(self) -> npt.NDArray[float]:
        right = np.cross(self._up_vec, self.direction)
        right /= np.linalg.norm(right)
        up = np.cross(self.direction, right)
        self._view_matrix[0:3, 0] = right
        self._view_matrix[0:3, 1] = up
        self._view_matrix[0:3, 2] = self.direction
        self._view_matrix[3, 0:3] = -self.position
        # self._view_matrix[0:3, 3] = -self.position

        return self._view_matrix

    @property
    def projection_matrix(self):
        s = 1.0 / math.tan(math.radians(self.fov) / 2.0)
        s1 = s / self.aspect_ratio
        self._projection_matrix[0, 0] = s
        self._projection_matrix[1, 1] = s1
        self._projection_matrix[2, 2] = self.clip_dist[1] / (self.clip_dist[0] - self.clip_dist[1])
        self._projection_matrix[2, 3] = -1
        self._projection_matrix[3, 2] = (self.clip_dist[0] * self.clip_dist[1]) / (self.clip_dist[0] - self.clip_dist[1])
        self._projection_matrix[3, 3] = 0
        return self._projection_matrix
