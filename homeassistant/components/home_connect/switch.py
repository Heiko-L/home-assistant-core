"""Provides a switch for Home Connect."""

import logging
from typing import Any

from homeconnect.api import HomeConnectError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_VALUE,
    ATTR_PRG_SWITCH,
    ATTR_STA_SWITCH,
    BSH_ACTIVE_PROGRAM,
    BSH_CHILD_LOCK_STATE,
    BSH_OPERATION_STATE,
    BSH_POWER_ON,
    BSH_POWER_STATE,
    DOMAIN,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect switch."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("switch", [])
            entity_list = [HomeConnectProgramSwitch(**d) for d in entity_dicts]
            entity_list += [HomeConnectPowerSwitch(device_dict[CONF_DEVICE])]
            entity_list += [HomeConnectChildLockSwitch(device_dict[CONF_DEVICE])]
            entities += entity_list
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectProgramSwitch(HomeConnectEntity, SwitchEntity):
    """Switch class for Home Connect."""

    def __init__(self, device, name, switch_type, key):
        """Initialize the entity."""
        if switch_type == ATTR_PRG_SWITCH:
          desc = " ".join(["Program", name.split(".")[-1]])
          if device.appliance.type == "WasherDryer":
              desc = " ".join(
                  ["Program", name.split(".")[-3], name.split(".")[-1]]
              )
        elif switch_type == ATTR_STA_SWITCH:
          desc = name
          self._key = key
        super().__init__(device, desc)

        self.name = name
        self._state = None
        self._remote_allowed = None
        self._type = switch_type

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return bool(self._state)


    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._type == ATTR_PRG_SWITCH:
          """Start the program."""
          _LOGGER.debug("Tried to turn on program %s", self.name)
          try:
            await self.hass.async_add_executor_job(
              self.device.appliance.start_program, self.name
            )
          except HomeConnectError as err:
            _LOGGER.error("Error while trying to start program: %s", err)
        elif self._type == ATTR_STA_SWITCH:
          _LOGGER.debug("Tried to turn on switch %s", self.name)
          try:
            await self.hass.async_add_executor_job(
              self.device.appliance.set_setting, self._key, "true"
            )
          except HomeConnectError as err:
              _LOGGER.error("Error while trying to turn on switch: %s", err)
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._type == ATTR_PRG_SWITCH:
          """Stop the program."""
          _LOGGER.debug("Tried to stop program %s", self.name)
          try:
            await self.hass.async_add_executor_job(self.device.appliance.stop_program)
          except HomeConnectError as err:
            _LOGGER.error("Error while trying to stop program: %s", err)
        elif self._type == ATTR_STA_SWITCH:
          _LOGGER.debug("Tried to turn off %s", self.name)
          try:
            await self.hass.async_add_executor_job(
              self.device.appliance.set_setting, self._key, "false"
            )
          except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn off: %s", err)
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""
        if self._type == ATTR_PRG_SWITCH:
          state = self.device.appliance.status.get(BSH_ACTIVE_PROGRAM, {})
          if state.get(ATTR_VALUE) == self.name:
              self._state = True
          else:
              self._state = False
          _LOGGER.debug("Updated, new state: %s", self._state)
        elif self._type == ATTR_STA_SWITCH:
          settings = self.device.appliance.get_settings()
          if settings.get(self._key) == "true":
            self._state = True
          else:
            self._state = False


class HomeConnectPowerSwitch(HomeConnectEntity, SwitchEntity):
    """Power switch class for Home Connect."""

    def __init__(self, device):
        """Initialize the entity."""
        super().__init__(device, "Power")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the device on."""
        _LOGGER.debug("Tried to switch on %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, BSH_POWER_STATE, BSH_POWER_ON
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn on device: %s", err)
            self._attr_is_on = False
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the device off."""
        _LOGGER.debug("tried to switch off %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting,
                BSH_POWER_STATE,
                self.device.power_off_state,
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn off device: %s", err)
            self._attr_is_on = True
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""
        if (
            self.device.appliance.status.get(BSH_POWER_STATE, {}).get(ATTR_VALUE)
            == BSH_POWER_ON
        ):
            self._attr_is_on = True
        elif (
            self.device.appliance.status.get(BSH_POWER_STATE, {}).get(ATTR_VALUE)
            == self.device.power_off_state
        ):
            self._attr_is_on = False
        elif self.device.appliance.status.get(BSH_OPERATION_STATE, {}).get(
            ATTR_VALUE, None
        ) in [
            "BSH.Common.EnumType.OperationState.Ready",
            "BSH.Common.EnumType.OperationState.DelayedStart",
            "BSH.Common.EnumType.OperationState.Run",
            "BSH.Common.EnumType.OperationState.Pause",
            "BSH.Common.EnumType.OperationState.ActionRequired",
            "BSH.Common.EnumType.OperationState.Aborting",
            "BSH.Common.EnumType.OperationState.Finished",
        ]:
            self._attr_is_on = True
        elif (
            self.device.appliance.status.get(BSH_OPERATION_STATE, {}).get(ATTR_VALUE)
            == "BSH.Common.EnumType.OperationState.Inactive"
        ):
            self._attr_is_on = False
        else:
            self._attr_is_on = None
        _LOGGER.debug("Updated, new state: %s", self._attr_is_on)


class HomeConnectChildLockSwitch(HomeConnectEntity, SwitchEntity):
    """Child lock switch class for Home Connect."""

    def __init__(self, device) -> None:
        """Initialize the entity."""
        super().__init__(device, "ChildLock")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch child lock on."""
        _LOGGER.debug("Tried to switch child lock on device: %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, BSH_CHILD_LOCK_STATE, True
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn on child lock on device: %s", err)
            self._attr_is_on = False
        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch child lock off."""
        _LOGGER.debug("Tried to switch off child lock on device: %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, BSH_CHILD_LOCK_STATE, False
            )
        except HomeConnectError as err:
            _LOGGER.error(
                "Error while trying to turn off child lock on device: %s", err
            )
            self._attr_is_on = True
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the switch's status."""
        self._attr_is_on = False
        if self.device.appliance.status.get(BSH_CHILD_LOCK_STATE, {}).get(ATTR_VALUE):
            self._attr_is_on = True
        _LOGGER.debug("Updated child lock, new state: %s", self._attr_is_on)
