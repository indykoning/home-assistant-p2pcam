"""Implement the P2PCam settings components"""


from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import CONF_NAME
import logging
from .const import DOMAIN, ATTR_HORIZONTAL, ATTR_VERTICAL, ATTR_TIMESTAMP
from .camera import P2PCamera


_LOGGER = logging.getLogger(__name__)


class P2PCamSwitch(SwitchEntity, RestoreEntity):
    def __init__(
        self,
        cam_id: str,
        cam_name: str,
        camera: P2PCamera,
        attr: str,
        setting_name: str,
        setting_icon: str
    ) -> None:
        # Home Assistant attributes
        self._attr_has_entity_name = True
        self._attr_name = setting_name
        self._device_id = cam_name
        self._attr_unique_id = f"{cam_id}_{setting_name.lower().replace(' ', '_')}"
        self._attr_icon = setting_icon
        self._state = False
        # Custom attributes
        self._cam = camera
        self._cam.register_availability_listener(self)
        self._attr = attr
        self._cam_id = cam_id

    @property
    def is_on(self) -> bool:
        """Return whether the switch is enabled or not"""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device infos"""

        return DeviceInfo(
            identifiers={(DOMAIN, self._cam_id)},
            name=self._device_id,
            manufacturer=DOMAIN,
            model=self._device_id,
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on"""

        # Update the switch status in Home Assistant and
        # the corresponding camera attribute
        self._state = True
        self._cam._attrs[self._attr] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off"""

        # Update the switch status in Home Assistant and
        # the corresponding camera attribute
        self._state = False
        self._cam._attrs[self._attr] = False
        self.async_write_ha_state()

    def schedule_update_ha_state(self) -> None:
        """Schedule an update of the entity state based on the main camera stream"""
        self._attr_available = self._cam._attr_available
        super().schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore previous state on startup"""

        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            self._state = True
            self._cam._attrs[self._attr] = True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Add settings entities from the entry"""

    data = hass.data[DOMAIN][entry.entry_id]

    # Retrieve the camera entity stored by camera platform setup
    camera_entity: P2PCamera = data["camera_entity"]

    # Add each setting entity
    async_add_entities([
        P2PCamSwitch(entry.entry_id, data[CONF_NAME], camera_entity, ATTR_HORIZONTAL, "Flip Horizontally", "mdi:flip-horizontal"),
        P2PCamSwitch(entry.entry_id, data[CONF_NAME], camera_entity, ATTR_VERTICAL, "Flip Vertically", "mdi:flip-vertical"),
        P2PCamSwitch(entry.entry_id, data[CONF_NAME], camera_entity, ATTR_TIMESTAMP, "Add Timestamp", "mdi:clock-plus-outline"),
    ])
