"""Constants for the P2PCam integration"""

from homeassistant.const import Platform

DOMAIN = "p2pcam"
PLATFORMS: list[Platform] = [Platform.CAMERA, Platform.SWITCH]

CONF_CAMERA_IP = "camera_ip"

ATTR_HORIZONTAL = "horizontal_flip"
ATTR_VERTICAL = "vertical_flip"
ATTR_TIMESTAMP = "add_timestamp"
