"""Implements the P2PCam camera component"""


from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_NAME
from homeassistant.components.camera import Camera
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import p2pcam
import logging
import threading
import time
from .const import DOMAIN, CONF_CAMERA_IP, ATTR_HORIZONTAL, ATTR_VERTICAL, ATTR_TIMESTAMP


_LOGGER = logging.getLogger(__name__)


class P2PCamera(Camera):
    def __init__(self, cam_id: str, cam_name: str, camera_ip: str) -> None:
        super().__init__()
        # Home Assistant attributes
        self._attr_has_entity_name = True
        self._attr_name = "Stream"
        self._device_id = cam_name
        self._attr_unique_id = cam_id
        self._attr_icon = "mdi:video"
        # Image transformation attributes (toggled by switch entities)
        self._attrs = {
            ATTR_HORIZONTAL: False,
            ATTR_VERTICAL: False,
            ATTR_TIMESTAMP: False,
        }
        self._cam_id = cam_id
        self._ip = camera_ip

        self._client = None
        # Image buffer for real time streaming
        self._latest_image = None
        self._image_lock = threading.Lock()
        self._stop_thread = False
        self._attr_available = True
        # Entities to notify when stream availability changes (e.g. switches)
        self._availability_listeners: list = []
        self._thread = threading.Thread(target=self._update_image_loop, daemon=True)
        self._thread.start()

    def register_availability_listener(self, entity) -> None:
        """Register an entity to be notified when stream availability changes"""
        self._availability_listeners.append(entity)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device infos"""

        return DeviceInfo(
            identifiers={(DOMAIN, self._cam_id)},
            name=self._device_id,
            manufacturer=DOMAIN,
            model=self._device_id,
        )

    def _apply_transforms(self, raw_frame: bytes) -> bytes:
        """Apply image transformations (flip, timestamp) based on switch states"""

        if not any(self._attrs.values()):
            return raw_frame

        input_frame = Image.open(BytesIO(raw_frame))

        if self._attrs[ATTR_VERTICAL]:
            input_frame = input_frame.transpose(Image.FLIP_TOP_BOTTOM)
        if self._attrs[ATTR_HORIZONTAL]:
            input_frame = input_frame.transpose(Image.FLIP_LEFT_RIGHT)

        if self._attrs[ATTR_TIMESTAMP]:
            draw = ImageDraw.Draw(input_frame)
            try:
                font = ImageFont.truetype("arial.ttf", 15)
            except Exception:
                font = ImageFont.load_default()
            draw.text(
                (10, 10),
                time.strftime("%Y-%m-%d  %H:%M:%S"),
                font=font,
                fill=(255, 255, 255),
                stroke_width=1,
                stroke_fill=(0, 0, 0),
            )

        output_frame = BytesIO()
        input_frame.save(output_frame, format="JPEG")
        return output_frame.getvalue()

    def _update_image_loop(self) -> None:
        """Continuously retrieve the latest image from the camera"""

        while not self._stop_thread:
            try:
                self._client = p2pcam.LanVideoClient(self._ip)
                for frame in self._client.stream(timeout=5):
                    if self._stop_thread:
                        break

                    if not self._attr_available:
                        self._attr_available = True
                        self.schedule_update_ha_state()
                        for listener in self._availability_listeners:
                            listener.schedule_update_ha_state()

                    with self._image_lock:
                        self._latest_image = self._apply_transforms(frame)

                if not self._stop_thread:
                    # Timeout reached, let the camera breathe a little
                    # before trying to reconnect
                    self._attr_available = False
                    self.schedule_update_ha_state()
                    for listener in self._availability_listeners:
                        listener.schedule_update_ha_state()
                    time.sleep(15)
            finally:
                if self._client:
                    try:
                        self._client.close()
                    finally:
                        self._client = None

    def camera_image(self, width=None, height=None) -> bytes | None:
        """Return the latest available image from the camera"""

        with self._image_lock:
            return self._latest_image

    def __del__(self) -> None:
        """"Properly stop the loop image retrieval"""

        self._stop_thread = True
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        if hasattr(self, "_thread"):
            self._thread.join(timeout=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Add the camera entity from the entry"""

    data = hass.data[DOMAIN][entry.entry_id]

    entity = P2PCamera(entry.entry_id, data[CONF_NAME], data[CONF_CAMERA_IP])

    # Store entity reference so switch platform can access it
    data["camera_entity"] = entity

    async_add_entities([entity])
