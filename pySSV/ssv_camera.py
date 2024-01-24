#  Copyright (c) 2023-2024 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
import logging
from enum import Enum
import numpy as np
import math
from abc import ABC, abstractmethod
from numpy import typing as npt
from typing import Tuple

from .ssv_logging import log


class MoveDir(Enum):
    """
    Represents a cardinal direction to move in.
    """
    NONE = 0
    FORWARD = 1
    BACKWARD = 2
    LEFT = 3
    RIGHT = 4
    UP = 5
    DOWN = 6


class SSVCamera:
    """
    A simple class representing a camera.
    """

    position: npt.NDArray[np.float32]
    """The camera's position in 3D space."""
    direction: npt.NDArray[np.float32]
    """A normalised vector pointing in the direction the camera is facing."""
    fov: float
    """The field of view of the camera in degrees."""
    clip_dist: Tuple[float, float]
    """The distances of the near and far clipping planes respectively."""
    aspect_ratio: float
    """The aspect ratio of the render buffer."""
    def __init__(self):
        self.position = np.array([0., 0., 0.], dtype=np.float32)
        self.direction = np.array([0., 0., -1.], dtype=np.float32)
        self.fov = 60
        self.clip_dist = (0.1, 1000.0)
        self.aspect_ratio = 1

        self._mouse_old_pos = np.array([0., 0.], dtype=np.int32)
        self._rotation = np.array([math.pi, 0.], dtype=np.float32)
        self._mouse_was_pressed = False
        self._view_matrix: npt.NDArray[np.float32] = np.identity(4, dtype=np.float32)  # type: ignore[annotation-unchecked]
        self._projection_matrix = np.identity(4, dtype=np.float32)
        self._up_vec = np.array([0., 1., 0.], dtype=np.float32)

    @staticmethod
    def _cross_3d(a: npt.NDArray[np.float32], b: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
        res: npt.NDArray[np.float32] = np.empty(3, dtype=np.float32)
        res[0] = a[1] * b[2] - a[2] * b[1]
        res[1] = -(a[0] * b[2] - a[2] * b[0])
        res[2] = a[0] * b[1] - a[1] * b[0]
        return res

    @staticmethod
    def _length_3d(a: npt.NDArray[np.float32]) -> float:
        return np.sqrt(a[0]*a[0] + a[1]*a[1] + a[2]*a[2])

    @property
    def rotation_matrix(self) -> npt.NDArray[np.float32]:
        """
        Gets the current view matrix of the camera, without the translation component.
        """
        right = SSVCamera._cross_3d(self.direction, self._up_vec)
        right /= SSVCamera._length_3d(right)
        up = SSVCamera._cross_3d(right, self.direction)
        up /= SSVCamera._length_3d(up)
        rot_matrix: npt.NDArray[np.float32] = np.identity(4, dtype=np.float32)
        rot_matrix[0:3, 0] = right
        rot_matrix[0:3, 1] = up
        rot_matrix[0:3, 2] = self.direction
        return rot_matrix

    @property
    def view_matrix(self) -> npt.NDArray[np.float32]:
        """
        Gets the current view matrix of the camera.
        """
        # noinspection PyTypeChecker
        self._view_matrix = np.array((
            (1, 0, 0, 0),
            (0, 1, 0, 0),
            (0, 0, 1, 0),
            (-self.position[0], -self.position[1], -self.position[2], 1),
        ), dtype=np.float32) @ self.rotation_matrix

        # noinspection PyTypeChecker
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
        self._projection_matrix[3, 2] = ((self.clip_dist[0] * self.clip_dist[1])
                                         / (self.clip_dist[0] - self.clip_dist[1]))
        self._projection_matrix[3, 3] = 0
        return self._projection_matrix


class SSVCameraController(SSVCamera, ABC):
    """
    A simple class representing a camera controller.
    """

    move_speed: float
    """The movement speed of the camera."""
    zoom_speed: float
    """The zooming speed of the camera."""
    pan_speed: float
    """The panning speed of the camera in radians per pixel of mouse movement."""

    def __init__(self):
        super().__init__()
        self.move_speed = 1.0
        self.zoom_speed = 0.1
        self.pan_speed = 0.005

    @abstractmethod
    def mouse_change(self, mouse_pos: Tuple[int, int], mouse_down: Tuple[bool, bool, bool]):
        ...

    @abstractmethod
    def move(self, direction: MoveDir, distance: float = 1.0):
        ...


class SSVLookCameraController(SSVCameraController):
    """
    A camera controller which supports mouse look controls.
    """
    def mouse_change(self, mouse_pos: Tuple[int, int], mouse_down: Tuple[bool, bool, bool]):
        """
        Updates the camera with a mouse event.

        :param mouse_pos: the new mouse position.
        :param mouse_down: whether the mouse button is pressed.
        """
        if mouse_down[0]:
            if not self._mouse_was_pressed:
                self._mouse_was_pressed = True
                self._mouse_old_pos[:] = mouse_pos
            else:
                self._rotation += (np.array(mouse_pos, dtype=np.int32) - self._mouse_old_pos) * self.pan_speed
                self._rotation[1] = min(max(self._rotation[1], -math.pi/2 + 1e-6), math.pi/2 - 1e-6)
                self.direction[0] = math.cos(self._rotation[0]) * math.cos(self._rotation[1])
                self.direction[1] = math.sin(self._rotation[1])
                self.direction[2] = math.sin(self._rotation[0]) * math.cos(self._rotation[1])
                self._mouse_old_pos[:] = mouse_pos
        else:
            self._mouse_was_pressed = False

    # noinspection DuplicatedCode
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
    _target_pos: npt.NDArray[np.float32]
    _orbit_dist: float

    def __init__(self):
        super().__init__()
        self._target_pos = np.array([0, 0, 0], dtype=np.float32)
        self._orbit_dist = 2

    @property
    def target_pos(self):
        """Gets or sets the point around which to orbit."""
        return self._target_pos

    @target_pos.setter
    def target_pos(self, value):
        self._target_pos = value
        self._update_direction_position()

    @property
    def orbit_dist(self):
        """Gets or sets the distance from the target position to orbit at."""
        return self._orbit_dist

    @orbit_dist.setter
    def orbit_dist(self, value):
        self._orbit_dist = value
        self._update_direction_position()

    def _update_direction_position(self):
        self.direction[0] = math.cos(self._rotation[0]) * math.cos(self._rotation[1])
        self.direction[1] = math.sin(self._rotation[1])
        self.direction[2] = math.sin(self._rotation[0]) * math.cos(self._rotation[1])

        self.position[:] = self._target_pos + self.direction * self._orbit_dist

    def mouse_change(self, mouse_pos: Tuple[int, int], mouse_down: Tuple[bool, bool, bool]):
        """
        Updates the camera with a mouse event.

        :param mouse_pos: the new mouse position.
        :param mouse_down: whether the mouse button is pressed.
        """
        if mouse_down[0] or mouse_down[1] or mouse_down[2]:
            if not self._mouse_was_pressed:
                self._mouse_was_pressed = True
                self._mouse_old_pos[:] = mouse_pos
        else:
            self._mouse_was_pressed = False

        if mouse_down[0]:
            # Orbit
            if self._mouse_was_pressed:
                self._rotation -= (np.array(mouse_pos, dtype=np.int32) - self._mouse_old_pos) * self.pan_speed
                self._rotation[1] = min(max(self._rotation[1], -math.pi/2 + 1e-6), math.pi/2 - 1e-6)

                self._update_direction_position()

                # log(f"view_mat=\n{np.transpose(self.view_matrix)}", severity=logging.INFO)
        elif mouse_down[2]:
            # Pan
            if self._mouse_was_pressed:
                mouse_delta = np.append((np.array(mouse_pos, dtype=np.float32) - self._mouse_old_pos) * self.pan_speed,
                                        (0, 0))
                self._target_pos += (self.rotation_matrix @ mouse_delta)[:3]

                self._update_direction_position()

                # log(f"view_mat=\n{np.transpose(self.view_matrix)}", severity=logging.INFO)
        elif mouse_down[1]:
            # Zoom
            pass

        self._mouse_old_pos[:] = mouse_pos

    def zoom(self, distance: float):
        """
        Updates the orbit distance with a zoom event.

        :param distance: how far to zoom in.
        """
        self.orbit_dist += self.orbit_dist * distance * self.zoom_speed
        self._update_direction_position()

    # noinspection DuplicatedCode
    def move(self, direction: MoveDir, distance: float = 1.0):
        """
        Updates the camera position with a movement event.

        :param direction: the direction to move in.
        :param distance: the distance to move.
        """
        dir_vec: npt.NDArray[np.float32] = np.zeros(4, dtype=np.float32)
        if direction == MoveDir.UP:
            dir_vec[1] = self.move_speed * distance
        elif direction == MoveDir.DOWN:
            dir_vec[1] = -self.move_speed * distance
        elif direction == MoveDir.RIGHT:
            dir_vec[0] = self.move_speed * distance
        elif direction == MoveDir.LEFT:
            dir_vec[0] = -self.move_speed * distance
        elif direction == MoveDir.FORWARD:
            dir_vec[2] = -self.move_speed * distance
        elif direction == MoveDir.BACKWARD:
            dir_vec[2] = self.move_speed * distance
        self._target_pos += (self.rotation_matrix @ dir_vec)[:3]
        self._update_direction_position()
        # log(f"Moved position: {self.position}", severity=logging.INFO)

