#  Copyright (c) 2023 Thomas Mathieson.
#  Distributed under the terms of the MIT license.
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Union
import numpy.typing as npt
import logging

from .ssv_logging import log

if TYPE_CHECKING:
    from .ssv_render_process_client import SSVRenderProcessClient
    from .ssv_shader_preprocessor import SSVShaderPreprocessor


def determine_texture_shape(data: npt.NDArray,
                            override_dtype: Optional[str],
                            treat_as_normalized_integer: bool = True) -> tuple[int, int, int, int, Optional[str]]:
    """
    Attempts to determine suitable texture parameters given an ndarray. This method returns (0,0,0,0,None) if a
    suitable format cannot be found.

    :param data: the ndarray to parse.
    :param override_dtype: optionally, a moderngl dtype string to use instead of the numpy dtype.
    :param treat_as_normalized_integer: when enabled, integer types (singed/unsigned) are treated as normalized
                                        integers by OpenGL, such that when the texture is sampled values in the
                                        texture are mapped to floats in the range [0, 1] or [-1, 1]. See:
                                        https://www.khronos.org/opengl/wiki/Normalized_Integer for more details.
    :return: (components, depth, height, width, dtype)
    """
    width, height, depth, components, dtype = (0, 0, 0, 0, None)
    if len(data.shape) == 1:
        # Simple 1D single component texture/buffer texture
        width = data.shape[0]
        height = 1
        components = 1
        depth = 0
    elif len(data.shape) == 2:
        if data.shape[1] <= 4:
            # 1D texture with up to 4 components
            width, components = data.shape
            height = 1
            depth = 1
        else:
            # 2D texture with 1 component
            width, height = data.shape
            components = 1
            depth = 1
    elif len(data.shape) == 3:
        if data.shape[2] <= 4:
            # 2D texture with up to 4 components
            width, height, components = data.shape
            depth = 1
        else:
            # 3D texture with 1 component
            width, height, depth = data.shape
            components = 1
    elif len(data.shape) == 4:
        if data.shape[3] <= 4:
            width, height, depth, components = data.shape
        else:
            # Too many dimensions
            log(f"Couldn't convert array with shape: {data.shape} into a texture! Too many dimensions.",
                severity=logging.ERROR)
    else:
        # Too many dimensions
        log(f"Couldn't convert array with shape: {data.shape} into a texture! Too many dimensions.",
            severity=logging.ERROR)

    if override_dtype is not None:
        if len(override_dtype) != 2:
            log(f"Invalid dtype '{override_dtype}' provided!", severity=logging.ERROR)
            return 0, 0, 0, 0, None
        try:
            if int(override_dtype[1]) != data.dtype.itemsize:
                log(f"Override dtype '{override_dtype}' item size does not match that of the input array "
                    f"({int(override_dtype[1])} != {data.dtype.itemsize})!", severity=logging.ERROR)
                return 0, 0, 0, 0, None
        except ValueError:
            log(f"Invalid dtype '{override_dtype}' provided!", severity=logging.ERROR)
            return 0, 0, 0, 0, None
        dtype = override_dtype

    conversion = {
        "b": "u",  # bool
        "u": "u",  # uint
        "i": "i",  # int
        "f": "f",  # float
        "c": "f",  # complex -> 2  floats
        "S": "u",  # byte string
        "V": "u",  # void
    }

    if dtype is None and data.dtype.kind in conversion:
        if not data.dtype.isnative:
            log(f"Unsupported dtype '{data.dtype}', must match system endianess.", severity=logging.ERROR)
            return 0, 0, 0, 0, None

        dtype = conversion[data.dtype.kind]
        if data.dtype.kind == "c" and (
                data.dtype.itemsize == 2 or data.dtype.itemsize == 4 or data.dtype.itemsize == 8):
            # Special case for complex data types
            if components <= 2:
                # Split complex values into two floats
                components *= 2
                dtype = f"{dtype}{data.dtype.itemsize / 2}"
            else:
                log(f"Unsupported dtype '{data.dtype}', complex types can only be used in 1 or 2 component textures!",
                    severity=logging.ERROR)
                return 0, 0, 0, 0, None
        elif data.dtype.itemsize == 1 or data.dtype.itemsize == 2 or data.dtype.itemsize == 4:
            dtype = f"{dtype}{data.dtype.itemsize}"
        else:
            log(f"Unsupported dtype '{data.dtype}', must have an itemsize of 1, 2, or 4!", severity=logging.ERROR)
            return 0, 0, 0, 0, None

        if treat_as_normalized_integer \
                and (data.dtype.itemsize == 1 or data.dtype.itemsize == 2) \
                and (dtype == "u" or dtype == "i"):
            dtype = "n" + dtype

    return components, depth, height, width, dtype


class SSVTexture:
    """
    A lightweight class representing a Texture object.
    """

    def __init__(self, texture_uid: Optional[int], render_process_client: SSVRenderProcessClient,
                 preprocessor: SSVShaderPreprocessor,
                 data: npt.NDArray, uniform_name: Optional[str], force_2d: bool = False, force_3d: bool = False,
                 override_dtype: Optional[str] = None, treat_as_normalized_integer: bool = True):
        """
        *Used Internally*

        Note that ``SSVTexture`` objects should be constructed using the factory method on either an ``SSVCanvas``.

        :param texture_uid: the UID to give this texture buffer. Set to ``None`` to generate one automatically.
        :param render_process_client: the render process connection belonging to the canvas.
        :param preprocessor: the preprocessor belonging to the canvas.
        :param data: a NumPy array containing the image data to copy to the texture.
        :param uniform_name: the name of the shader uniform to associate this texture with.
        :param force_2d: when set, forces the texture to be treated as 2-dimensional, even if it could be represented
                         by a 1D texture. This only applies in the ambiguous case where a 2D single component texture
                         has a height <= 4 (eg: ``np.array([[0.0, 0.1, 0.2], [0.3, 0.4, 0.5], [0.6, 0.7, 0.8]])``),
                         with this parameter set to ``False``, the array would be converted to a 1D texture with a
                         width of 3 and 3 components; setting this to ``True`` ensures that it becomes a 3x3 texture
                         with 1 component.
        :param force_3d: when set, forces the texture to be treated as 3-dimensional, even if it could be represented
                         by a 2D texture. See the description of the ``force_2d`` parameter for a full explanation.
        :param override_dtype: optionally, a moderngl datatype to force on the texture.
        :param treat_as_normalized_integer: when enabled, integer types (singed/unsigned) are treated as normalized
                                            integers by OpenGL, such that when the texture is sampled values in the
                                            texture are mapped to floats in the range [0, 1] or [-1, 1]. See:
                                            https://www.khronos.org/opengl/wiki/Normalized_Integer for more details.
        """
        self._texture_uid = id(self) if texture_uid is None else texture_uid
        self._render_process_client = render_process_client
        self._preprocessor = preprocessor
        self._uniform_name = uniform_name
        if force_2d and len(data.shape) == 2 and data.shape[1] <= 4:
            data = data.reshape((*data.shape, 1))
        if force_3d and len(data.shape) == 3 and data.shape[2] <= 4:
            data = data.reshape((*data.shape, 1))

        (self._components, self._depth, self._height, self._width, self._dtype) = \
            determine_texture_shape(data, override_dtype, treat_as_normalized_integer)

        sampler_prefix = ""
        if not treat_as_normalized_integer:
            if data.dtype.kind in {"f", "c"}:
                sampler_prefix = ""
            elif data.dtype.kind in {"b", "u", "S", "V"}:
                sampler_prefix = "u"
            else:
                sampler_prefix = "i"
        sampler_type = f"{sampler_prefix}sampler3D" if self._depth > 1 else f"{sampler_prefix}sampler2D"

        self._render_process_client.update_texture(self._texture_uid, data, uniform_name, override_dtype, None,
                                                   treat_as_normalized_integer)
        self._preprocessor.add_dynamic_uniform(self._uniform_name, sampler_type)

    @property
    def texture_uid(self) -> int:
        """
        Gets the internal UID of this texture object.
        """
        return self._texture_uid

    @property
    def uniform_name(self) -> str:
        """
        Gets the shader uniform name associated with this texture.
        """
        return self._uniform_name

    @property
    def components(self) -> int:
        """
        Gets the number of components for a single pixel (RGB=3, RGBA=4). Always at least 1, never more than 4.
        """
        return self._components

    @property
    def depth(self) -> int:
        """
        Gets the depth of the texture. Always returns 1 for 1D and 2D textures.
        """
        return self._depth

    @property
    def height(self) -> int:
        """
        Gets the height of the texture. Always returns 1 for 1D textures.
        """
        return self._height

    @property
    def width(self) -> int:
        """
        Gets the width of the texture.
        """
        return self._width

    @property
    def dtype(self) -> str:
        """
        Gets the data type of a single component in the texture.

        See https://moderngl.readthedocs.io/en/latest/topics/texture_formats.html for a full list of available data
        types.
        """
        return self._dtype

    @property
    def repeat_x(self) -> None:
        """
        Sets whether the texture should repeat or be clamped in the x-axis.
        """
        return None

    @repeat_x.setter
    def repeat_x(self, value: bool):
        self._render_process_client.update_texture_sampler(self._texture_uid, repeat_x=value)

    @property
    def repeat_y(self) -> None:
        """
        Sets whether the texture should repeat or be clamped in the y-axis.
        """
        return None

    @repeat_y.setter
    def repeat_y(self, value: bool):
        self._render_process_client.update_texture_sampler(self._texture_uid, repeat_y=value)

    @property
    def linear_filtering(self) -> None:
        """
        Sets whether the texture should use nearest neighbour (``False``) or linear (``True``) interpolation.
        """
        return None

    @linear_filtering.setter
    def linear_filtering(self, value: bool):
        self._render_process_client.update_texture_sampler(self._texture_uid, linear_filtering=value)

    @property
    def linear_mipmap_filtering(self) -> None:
        """
        Sets whether different mipmap levels should blend linearly (``True``) or not (``False``).
        """
        return None

    @linear_mipmap_filtering.setter
    def linear_mipmap_filtering(self, value: bool):
        self._render_process_client.update_texture_sampler(self._texture_uid, linear_mipmap_filtering=value)

    @property
    def anisotropy(self) -> None:
        """
        Sets the number of anisotropy samples to use. (minimum of 1 = disabled, maximum of 16)
        """
        return None

    @anisotropy.setter
    def anisotropy(self, value: int):
        self._render_process_client.update_texture_sampler(self._texture_uid, anisotropy=value)

    def update_texture(self, data: npt.NDArray,
                       rect: Optional[Union[tuple[int, int, int, int], tuple[int, int, int, int, int, int]]] = None):
        """
        Updates the contents of this texture from the NumPy array provided.

        :param data: a NumPy array containing the image data to copy to the texture.
        :param rect: optionally, a rectangle (left, top, right, bottom) specifying the area of the target texture to
                     update.
        """
        self._render_process_client.update_texture(self._texture_uid, data, None, None, rect)

    def build_mipmaps(self):
        """
        Generates mipmaps for the texture.
        """
        self._render_process_client.update_texture_sampler(self._texture_uid, build_mip_maps=True)

    def release(self):
        """
        Destroys this texture object and releases the associated GPU resources.
        """
        self._render_process_client.delete_texture(self._texture_uid)

    def __del__(self):
        self.release()
