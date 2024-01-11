#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
import typing
from enum import Enum
import numpy as np
import math
from abc import ABC, abstractmethod
from numpy import typing as npt

from .ssv_logging import log


class MoveDir(Enum):
    """
    Represents a cardinal direction to move in.
    """
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

    position: npt.NDArray[3]
    """The camera's position in 3D space."""
    direction: npt.NDArray[3]
    """A normalised vector pointing in the direction the camera is facing."""
    fov: float
    """The field of view of the camera in degrees."""
    clip_dist: tuple[float, float]
    """The distances of the near and far clipping planes respectively."""
    aspect_ratio: float
    """The aspect ratio of the render buffer."""
    def __init__(self):
        self.position = np.array([0., 0., 0.])
        self.direction = np.array([0., 0., -1.])
        self.fov = 60
        self.clip_dist = (0.1, 1000.0)
        self.aspect_ratio = 1

        self._mouse_old_pos = np.array([0., 0.])
        self._rotation = np.array([math.pi, 0.])
        self._mouse_was_pressed = False
        self._view_matrix = np.identity(4)
        self._projection_matrix = np.identity(4)
        self._up_vec = np.array([0., 1., 0.])

    @property
    def view_matrix(self) -> npt.NDArray[float]:
        """
        Gets the current view matrix of the camera.
        """
        right = np.cross(self.direction, self._up_vec)
        right /= np.linalg.norm(right)
        up = np.cross(right, self.direction)
        up /= np.linalg.norm(up)
        self._view_matrix = np.identity(4, dtype=np.float32)
        self._view_matrix[0:3, 0] = right
        self._view_matrix[0:3, 1] = up
        self._view_matrix[0:3, 2] = self.direction
        self._view_matrix = np.array((
            (1, 0, 0, 0),
            (0, 1, 0, 0),
            (0, 0, 1, 0),
            (-self.position[0], -self.position[1], -self.position[2], 1),
        ), dtype=np.float32) @ self._view_matrix

        return self._view_matrix

    @property
    def projection_matrix(self):
        """
        Gets the current projection matrix of the camera.
        """
        s = 1.0 / math.tan(math.radians(self.fov) / 2.0)
        s1 = s / self.aspect_ratio
        self._projection_matrix[0, 0] = s
        self._projection_matrix[1, 1] = s1
        self._projection_matrix[2, 2] = self.clip_dist[1] / (self.clip_dist[0] - self.clip_dist[1])
        self._projection_matrix[2, 3] = -1
        self._projection_matrix[3, 2] = (self.clip_dist[0] * self.clip_dist[1]) / (self.clip_dist[0] - self.clip_dist[1])
        self._projection_matrix[3, 3] = 0
        return self._projection_matrix


class SSVCameraController(SSVCamera, ABC):
    """
    A simple class representing a camera controller.
    """

    move_speed: float
    """The movement speed of the camera."""
    pan_speed: float
    """The panning speed of the camera in radians per pixel of mouse movement."""

    def __init__(self):
        super().__init__()
        self.move_speed = 0.1
        self.pan_speed = 0.005

    @abstractmethod
    def mouse_change(self, mouse_pos: list[int], mouse_down: bool):
        ...

    @abstractmethod
    def move(self, direction: MoveDir, distance: float = 1.0):
        ...


class SSVLookCameraController(SSVCameraController):
    """
    A camera controller which supports mouse look controls.
    """
    def mouse_change(self, mouse_pos: list[int], mouse_down: bool):
        """
        Updates the camera with a mouse event.

        :param mouse_pos: the new mouse position.
        :param mouse_down: whether the mouse button is pressed.
        """
        if mouse_down:
            if not self._mouse_was_pressed:
                self._mouse_was_pressed = True
                self._mouse_old_pos[:] = mouse_pos
            else:
                self._rotation += (np.array(mouse_pos) - self._mouse_old_pos) * self.pan_speed
                self._rotation[1] = min(max(self._rotation[1], -math.pi/2), math.pi/2)
                self.direction[0] = math.cos(self._rotation[0]) * math.cos(self._rotation[1])
                self.direction[1] = math.sin(self._rotation[1])
                self.direction[2] = math.sin(self._rotation[0]) * math.cos(self._rotation[1])
                self._mouse_old_pos[:] = mouse_pos
        else:
            self._mouse_was_pressed = False

    def move(self, direction: MoveDir, distance: float = 1.0):
        """
        Updates the camera position with a movement event.

        :param direction: the direction to move in.
        :param distance: the distance to move.
        """
        if direction == MoveDir.UP:
            self.position[1] += self.move_speed * distance
        elif direction == MoveDir.DOWN:
            self.position[1] -= self.move_speed * distance
        elif direction == MoveDir.RIGHT:
            self.position[0] += self.move_speed * distance
        elif direction == MoveDir.LEFT:
            self.position[0] -= self.move_speed * distance
        elif direction == MoveDir.FORWARD:
            self.position[2] += self.move_speed * distance
        elif direction == MoveDir.BACKWARD:
            self.position[2] -= self.move_speed * distance
        # log(f"Moved position: {self.position}", severity=logging.INFO)


class SSVOrbitCameraController(SSVCameraController):
    """
    A camera controller which supports orbiting around a given target.
    """
    target_pos: npt.NDArray[3]
    """The point around which to orbit."""
    orbit_dist: float
    """The distance from the target position to orbit at."""

    def __init__(self):
        super().__init__()
        self.target_pos = np.array([0, 0, 0])
        self.orbit_dist = 2

    def _update_direction_position(self):
        self.direction[0] = math.cos(self._rotation[0]) * math.cos(self._rotation[1])
        self.direction[1] = math.sin(self._rotation[1])
        self.direction[2] = math.sin(self._rotation[0]) * math.cos(self._rotation[1])

        self.position[:] = self.target_pos + self.direction * self.orbit_dist

    def mouse_change(self, mouse_pos: list[int], mouse_down: bool):
        """
        Updates the camera with a mouse event.

        :param mouse_pos: the new mouse position.
        :param mouse_down: whether the mouse button is pressed.
        """
        if mouse_down:
            if not self._mouse_was_pressed:
                self._mouse_was_pressed = True
                self._mouse_old_pos[:] = mouse_pos
            else:
                self._rotation -= (np.array(mouse_pos) - self._mouse_old_pos) * self.pan_speed
                self._rotation[1] = min(max(self._rotation[1], -math.pi/2), math.pi/2)

                self._update_direction_position()

                # log(f"view_mat=\n{np.transpose(self.view_matrix)}", severity=logging.INFO)

                self._mouse_old_pos[:] = mouse_pos
        else:
            self._mouse_was_pressed = False

    def zoom(self, distance: float):
        """
        Updates the orbit distance with a zoom event.

        :param distance: how far to zoom in.
        """
        self.orbit_dist += self.orbit_dist * distance * self.move_speed
        self._update_direction_position()

    def move(self, direction: MoveDir, distance: float = 1.0):
        """
        Updates the camera position with a movement event.

        :param direction: the direction to move in.
        :param distance: the distance to move.
        """
        if direction == MoveDir.UP:
            self.target_pos[1] += self.move_speed * distance
        elif direction == MoveDir.DOWN:
            self.target_pos[1] -= self.move_speed * distance
        elif direction == MoveDir.RIGHT:
            self.target_pos[0] += self.move_speed * distance
        elif direction == MoveDir.LEFT:
            self.target_pos[0] -= self.move_speed * distance
        elif direction == MoveDir.FORWARD:
            self.target_pos[2] += self.move_speed * distance
        elif direction == MoveDir.BACKWARD:
            self.target_pos[2] -= self.move_speed * distance
        # log(f"Moved position: {self.position}", severity=logging.INFO)

