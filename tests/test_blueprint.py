"""Test the real YAML guard offline without calling Home Assistant services."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
import math
import copy
from jinja2.nativetypes import NativeEnvironment
import yaml

ROOT = Path(__file__).resolve().parents[1]


class BlueprintInput(str):
    pass


class BlueprintLoader(yaml.SafeLoader):
    pass


BlueprintLoader.add_constructor('!input', lambda loader, node: BlueprintInput(loader.construct_scalar(node)))
BLUEPRINT = yaml.load((ROOT / 'blueprints/automation/ecoflow_safe_shutdown.yaml').read_text(encoding='utf-8'), Loader=BlueprintLoader)
DEVICE = 'simulated_ecoflow_device'
INPUTS = {key: value['default'] for key, value in BLUEPRINT['blueprint']['input'].items() if 'default' in value}


INPUTS.update(ups_device=DEVICE, shutdown_enabled=True)


def substitute(value):
    if isinstance(value, BlueprintInput):
        return INPUTS[value]
    if isinstance(value, dict):
        return {key: substitute(item) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item) for item in value]
    return value


AUTOMATION = substitute({key: value for key, value in BLUEPRINT.items() if key != 'blueprint'})
GUARD = AUTOMATION['triggers'][0]['value_template']
P = 'sensor.test_ecoflow_'
FLOOR = 'number.test_ecoflow_min_discharge_level'
SWITCH = 'switch.test_ecoflow_ac_enabled'
NOW = datetime(2026, 11, 7, 22, tzinfo=timezone.utc)
MEASUREMENTS = ['battery_level', 'main_battery_level', 'ac_in_power',
                'ac_out_power', 'total_in_power', 'total_out_power']

class States(dict):
    def __call__(self, entity):
        return self[entity].state if entity in self else 'unknown'

def fixture():
    values = dict(battery_level='29', main_battery_level='29', ac_in_power='0',
                  ac_out_power='45', total_in_power='0', total_out_power='45',
                  status='online', battery_charging_state='discharging')
    states = States({P + key: SimpleNamespace(state=value, last_reported=NOW)
                     for key, value in values.items()})
    states[FLOOR] = SimpleNamespace(state='20', last_reported=NOW - timedelta(days=2))
    states[SWITCH] = SimpleNamespace(state='on', last_reported=NOW)
    return states

def evaluate(states, device_entities=None, **settings):
    env = NativeEnvironment()
    def is_number(value):
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False
    ids = list(fixture()) if device_entities is None else device_entities
    env.globals.update(states=states, now=lambda: NOW,
                       device_entities=lambda device: ids if device == DEVICE else [],
                       device_id=lambda entity: DEVICE if entity == P + 'battery_level' else None,
                       is_number=is_number,
                       is_state=lambda entity, value: states(entity) == value,
                       as_timestamp=lambda value, default=0: value.timestamp()
                       if isinstance(value, datetime) else default)
    result = env.from_string(GUARD).render(**(AUTOMATION['variables'] | settings))
    return result is True or (isinstance(result, str) and result.strip() == 'True')

class ShutdownTests(unittest.TestCase):
    def test_thresholds(self):
        for floor, battery, expected in [(20, 30, True), (20, 30.1, False),
                                         (0, 20, True), (0, 20.1, False),
                                         (30, 40, True), (31, 30, False),
                                         (-1, 10, False), (20, 0, False)]:
            with self.subTest(floor=floor, battery=battery):
                states = fixture()
                states[FLOOR].state = str(floor)
                for key in ['battery_level', 'main_battery_level']:
                    states[P + key].state = str(battery)
                self.assertEqual(evaluate(states), expected)

    def test_invalid_and_missing_measurements(self):
        for entity in [P + key for key in MEASUREMENTS] + [FLOOR]:
            for invalid in ['unknown', 'unavailable', '', 'garbage', '-1', 'nan', 'inf', '-inf']:
                with self.subTest(entity=entity, invalid=invalid):
                    states = fixture()
                    states[entity].state = invalid
                    self.assertFalse(evaluate(states))
            states = fixture()
            del states[entity]
            self.assertFalse(evaluate(states))

    def test_freshness(self):
        for key in MEASUREMENTS:
            for age in [181, 600, -1]:
                with self.subTest(key=key, age=age):
                    states = fixture()
                    states[P + key].last_reported = NOW - timedelta(seconds=age)
                    self.assertFalse(evaluate(states))
        states = fixture()
        for key in MEASUREMENTS:
            states[P + key].last_reported = NOW - timedelta(seconds=180)
        self.assertTrue(evaluate(states))

    def test_contradictions_and_mains_recovery(self):
        for key, value in [('status', 'offline'), ('status', 'unavailable'),
                           ('battery_charging_state', 'charging'),
                           ('battery_charging_state', 'idle'),
                           ('battery_charging_state', 'unknown'),
                           ('main_battery_level', '25'), ('main_battery_level', '31'),
                           ('ac_in_power', '1'), ('ac_in_power', '45'),
                           ('total_in_power', '1'), ('ac_out_power', '0'),
                           ('total_out_power', '0')]:
            with self.subTest(key=key, value=value):
                states = fixture()
                states[P + key].state = value
                self.assertFalse(evaluate(states))
        for value in ['off', 'unknown', 'unavailable']:
            states = fixture()
            states[SWITCH].state = value
            self.assertFalse(evaluate(states))

    def test_continuous_confirmation_and_final_recheck(self):
        trigger = AUTOMATION['triggers'][0]
        self.assertEqual(trigger['trigger'], 'template')
        self.assertEqual(trigger['for'], {'seconds': 120})
        actions = AUTOMATION['actions']
        self.assertEqual(actions[0], {'condition': 'trigger', 'id': [trigger['id'], 'retry_startup']})
        self.assertEqual(actions[2]['value_template'], GUARD)
        final = actions[-1]['choose'][0]
        self.assertEqual(final['conditions'][0]['value_template'], GUARD)
        self.assertEqual(final['sequence'], [{'action': 'hassio.host_shutdown', 'data': {}}])
        states = fixture()
        self.assertTrue(evaluate(states))
        states[P + 'ac_in_power'].state = '45'
        self.assertFalse(evaluate(states))
        states[P + 'ac_in_power'].state = 'unavailable'
        self.assertFalse(evaluate(states))

    def test_shutdown_requires_explicit_arming(self):
        self.assertIs(BLUEPRINT['blueprint']['input']['shutdown_enabled']['default'], False)
        for enabled in [False, None, 'false', 'true', 0, 1]:
            with self.subTest(enabled=enabled):
                self.assertFalse(evaluate(fixture(), shutdown_enabled=enabled))
        self.assertTrue(evaluate(fixture(), shutdown_enabled=True))

    def test_resolves_one_complete_set_on_selected_device(self):
        remapped = States({entity.replace('test_ecoflow_', 'other_ups_'): copy.copy(value)
                           for entity, value in fixture().items()})
        self.assertTrue(evaluate(remapped, device_entities=list(remapped)))
        self.assertFalse(evaluate(remapped, device_entities=list(remapped) + list(fixture())))
        self.assertFalse(evaluate(remapped, device_entities=list(remapped)[:-1]))
        self.assertFalse(evaluate(remapped, device_entities=list(remapped), ups_device='wrong'))
        self.assertTrue(evaluate(fixture(), ups_device='', legacy_battery=P + 'battery_level'))

    def test_rtc_startup_cancels_on_any_guard_failure(self):
        startup = AUTOMATION['actions'][1]['then']
        self.assertEqual(startup[1]['then'][0]['action'], 'ecoflow_rtc.cancel_wake')
        self.assertEqual(startup[2]['wait_template'], GUARD)
        inverse = startup[4]['wait_for_trigger'][0]['value_template']
        self.assertEqual(inverse, GUARD)
        states = fixture()
        self.assertFalse(evaluate(states, wait_for_invalid=True))
        states[P + 'ac_in_power'].state = '45'
        self.assertTrue(evaluate(states, wait_for_invalid=True))
        self.assertFalse(evaluate(states, wait_for_invalid=False))
        schedule = AUTOMATION['actions'][3]['then'][0]['then'][0]
        self.assertEqual(schedule['action'], 'ecoflow_rtc.schedule_wake')
        self.assertTrue(schedule['continue_on_error'])
        self.assertEqual(schedule['data']['retry_minutes'], 15)
        self.assertFalse(INPUTS['retry_enabled'])

    def test_configurable_report_age(self):
        states = fixture()
        states[P + 'battery_level'].last_reported = NOW - timedelta(seconds=61)
        self.assertFalse(evaluate(states, max_age_seconds=60))
        self.assertTrue(evaluate(states, max_age_seconds=61))

    def test_missing_or_invalid_discrete_states(self):
        for entity in [P + 'status', P + 'battery_charging_state', SWITCH]:
            for invalid in ['unknown', 'unavailable', '', 'garbage']:
                states = fixture()
                states[entity].state = invalid
                self.assertFalse(evaluate(states))
            states = fixture()
            del states[entity]
            self.assertFalse(evaluate(states))

    def test_blueprint_wiring_and_defaults(self):
        self.assertEqual(AUTOMATION['variables'], AUTOMATION['trigger_variables'])
        self.assertTrue(INPUTS['shutdown_enabled'])
        self.assertEqual(BLUEPRINT['blueprint']['input']['confirmation_seconds']['default'], 120)
        self.assertEqual(BLUEPRINT['blueprint']['input']['max_age_seconds']['default'], 180)
        self.assertEqual(AUTOMATION['mode'], 'single')
        self.assertEqual(AUTOMATION['max_exceeded'], 'silent')

if __name__ == '__main__':
    unittest.main()
