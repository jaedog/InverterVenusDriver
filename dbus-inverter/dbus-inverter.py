#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""dbus-inverter.py: Monitors Shelly EM power meters for Grid and AC Loads. Publishes to the vebus inverter dbus
    to simulate an inverter with Victron Venus OS. """

# requires: pip install ShellyPy

__author__      = "github username: jaedog"
__copyright__   = "Copyright 2021"
__license__     = "MIT"
__version__     = "0.1"

import os
import sys
import signal
from timeit import default_timer as timer
import time
from datetime import datetime, timedelta
import json
import requests
import threading
import logging
import yaml
from requests.auth import HTTPDigestAuth

import ShellyPy

from dbus.mainloop.glib import DBusGMainLoop
import dbus
import gobject

# Victron packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext', 'velib_python'))
from vedbus import VeDbusService
from ve_utils import get_vrm_portal_id, exit_on_error
from dbusmonitor import DbusMonitor

softwareVersion = '1.1'
logger = logging.getLogger("dbus-inverter")

# global logger for all modules imported here
#logger = logging.getLogger()

logger.setLevel(logging.DEBUG)
#logger.setLevel(logging.INFO)

driver_start_time = datetime.now()

config = None
try :
  dir_path = os.path.dirname(os.path.realpath(__file__))
  with open(dir_path + "/dbus-inverter.yaml", "r") as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)
  #print(config)
  if (config['ShellyLoads']['address'] == "IP_ADDR"):
    print("dbus-inverter.yaml file using invalid default values.")
    logger.info("dbus-inverter.yaml file using invalid default values.")
    raise

except :
  print("dbus-watcher.yaml file not found or correct.")
  logger.info("dbus-watcher.yaml file not found or correct.")
  sys.exit()


host_ac_loads = config['ShellyLoads']['address']
host_grid = config['ShellyGrid']['address']
host_grid_ctl = config['ShellyGridCtl']['address']

keep_running = True

# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
DBusGMainLoop(set_as_default=True)

# callback that gets called every time a dbus value has changed
def _dbus_value_changed(dbusServiceName, dbusPath, dict, changes, deviceInstance):
  pass

# Why this dummy? Because DbusMonitor expects these values to be there, even though we don't
# need them. So just add some dummy data. This can go away when DbusMonitor is more generic.
dummy = {'code': None, 'whenToLog': 'configChange', 'accessLevel': None}
dbus_tree = {'com.victronenergy.system': 
  {'/Dc/Battery/Soc': dummy, '/Dc/Battery/Current': dummy, '/Dc/Battery/Power': dummy, \
   '/Dc/Battery/Voltage': dummy, '/Dc/Battery/ConsumedAmphours': dummy, '/Dc/Battery/TimeToGo': dummy, \
    '/Dc/Pv/Current': dummy, '/Ac/PvOnOutput/L1/Power': dummy, '/Ac/PvOnOutput/L2/Power': dummy, }}

dbusmonitor = DbusMonitor(dbus_tree, valueChangedCallback=_dbus_value_changed)

# connect and register to dbus
driver = {
	'name'        : "AC Inverter",
	'servicename' : "acinverter",
	'instance'    : 264,
	'id'          : 127,
	'version'     : 100,
}

#-------------------
def create_dbus_service():
  dbusservice = VeDbusService('com.victronenergy.vebus.acinverter')
  dbusservice.add_mandatory_paths(
  processname=__file__,
  processversion=0.1,
  connection='com.victronenergy.vebus.acinverter',
  deviceinstance=driver['instance'],
  productid=driver['id'],
  productname=driver['name'],
  firmwareversion=driver['version'],
  hardwareversion=driver['version'],
  connected=1)

  return dbusservice

dbusservice = create_dbus_service()

# /SystemState/State   ->   0: Off
#                      ->   1: Low power
#                      ->   2: VE.Bus Fault condition
#                      ->   3: Bulk charging
#                      ->   4: Absorption charging
#                      ->   5: Float charging
#                      ->   6: Storage mode
#                      ->   7: Equalisation charging
#                      ->   8: Passthru
#                      ->   9: Inverting
#                      ->  10: Assisting
#                      -> 256: Discharging
#                      -> 257: Sustain
dbusservice.add_path('/State',                   0)
dbusservice.add_path('/Mode',                    3)
dbusservice.add_path('/Ac/PowerMeasurementType', 0)

# Create the inverter/charger paths
dbusservice.add_path('/Ac/Out/L1/P',            -1)
dbusservice.add_path('/Ac/Out/L2/P',            -1)
dbusservice.add_path('/Ac/Out/L1/I',            -1)
dbusservice.add_path('/Ac/Out/L2/I',            -1)
dbusservice.add_path('/Ac/Out/L1/V',            -1)
dbusservice.add_path('/Ac/Out/L2/V',            -1)
dbusservice.add_path('/Ac/Out/L1/F',            -1)
dbusservice.add_path('/Ac/Out/L2/F',            -1)
dbusservice.add_path('/Ac/Out/P',               -1)
dbusservice.add_path('/Ac/ActiveIn/L1/P',       -1)
dbusservice.add_path('/Ac/ActiveIn/L2/P',       -1)
dbusservice.add_path('/Ac/ActiveIn/P',          -1)
dbusservice.add_path('/Ac/ActiveIn/L1/V',       -1)
dbusservice.add_path('/Ac/ActiveIn/L2/V',       -1)
dbusservice.add_path('/Ac/ActiveIn/L1/F',       -1)
dbusservice.add_path('/Ac/ActiveIn/L2/F',       -1)
dbusservice.add_path('/Ac/ActiveIn/L1/I',       -1)
dbusservice.add_path('/Ac/ActiveIn/L2/I',       -1)
dbusservice.add_path('/Ac/ActiveIn/Connected',   0)
dbusservice.add_path('/Ac/ActiveIn/ActiveInput', 0)
dbusservice.add_path('/VebusError',              0)
dbusservice.add_path('/Dc/0/Voltage',           -1)
dbusservice.add_path('/Dc/0/Power',             -1)
dbusservice.add_path('/Dc/0/Current',           -1)
dbusservice.add_path('/Ac/NumberOfPhases',       2)
dbusservice.add_path('/Alarms/GridLost',         0)

# /VebusChargeState  <- 1. Bulk
#                       2. Absorption
#                       3. Float
#                       4. Storage
#                       5. Repeat absorption
#                       6. Forced absorption
#                       7. Equalise
#                       8. Bulk stopped
dbusservice.add_path('/VebusChargeState',        0)

# Some attempts at logging consumption. Float of kwhr since driver start (i think)
dbusservice.add_path('/Energy/GridToDc',         0)
dbusservice.add_path('/Energy/GridToAcOut',      0)
dbusservice.add_path('/Energy/DcToAcOut',        0)
dbusservice.add_path('/Energy/AcIn1ToInverter',  0)
dbusservice.add_path('/Energy/AcIn1ToAcOut',     0)
dbusservice.add_path('/Energy/InverterToAcOut',  0)
dbusservice.add_path('/Energy/Time',       timer())

def ac_grid_control(enabled) :
  ac_grid_ctrl = ShellyPy.Shelly(host_grid_ctl, timeout=1)
  ac_grid_ctrl.relay(0, turn=enabled)

soc = 50.0 # set to sane value so we don't trigger relay on init

#----------
def ac_grid_handler():
  logger.debug("start ac_grid thread")
  ac_grid = None
  ac_grid_ctrl = None
  zero_export_countdown = 5
  storm_warning = False

  while 1:
    ac_in_l1_power = 0
    ac_in_l2_power = 0
    ac_in_l1_voltage = 0
    ac_in_l2_voltage = 0
    ac_in_l1_current = 0
    ac_in_l2_current = 0
    ac_in_freq = 0

    #global ac_grid
    try:
      if (ac_grid == None) :
        ac_grid = ShellyPy.Shelly(host_grid, timeout=1)

      ac_in_emeter_l1 = ac_grid.emeter(0)
      ac_in_emeter_l2 = ac_grid.emeter(1)

      #print(ac_in_emeter_l1)
      ac_in_l1_power = ac_in_emeter_l1['power']
      ac_in_l2_power = ac_in_emeter_l2['power']
      ac_in_l1_voltage = ac_in_emeter_l1['voltage']
      ac_in_l2_voltage = ac_in_emeter_l2['voltage']

      if (ac_in_l1_voltage > 0) :
        ac_in_l1_current = int(ac_in_l1_power / ac_in_l1_voltage)

      if (ac_in_l2_voltage > 0) :
        ac_in_l2_current = int(ac_in_l2_power / ac_in_l2_voltage)

      ac_in_freq = 60

    except requests.exceptions.ConnectionError as e:
      pass
      time.sleep(3)
      #print(e)

    ac_in_total_power = ac_in_l1_power + ac_in_l2_power
    dbusservice["/Ac/ActiveIn/L1/P"] = ac_in_l1_power
    dbusservice["/Ac/ActiveIn/L2/P"] = ac_in_l2_power
    dbusservice["/Ac/ActiveIn/P"] = ac_in_total_power
    dbusservice["/Ac/ActiveIn/L1/V"] = ac_in_l1_voltage
    dbusservice["/Ac/ActiveIn/L2/V"] = ac_in_l2_voltage
    dbusservice["/Ac/ActiveIn/L1/F"] = ac_in_freq
    dbusservice["/Ac/ActiveIn/L2/F"] = ac_in_freq
    dbusservice["/Ac/ActiveIn/L1/I"] = ac_in_l1_current
    dbusservice["/Ac/ActiveIn/L2/I"] = ac_in_l2_current

    if (ac_in_l1_voltage > 100) :
      # if grid is connected
      dbusservice["/Ac/ActiveIn/Connected"] = 1
      dbusservice["/Ac/ActiveIn/ActiveInput"] = 0
      dbusservice["/Alarms/GridLost"]  = 0
    else :
      # if grid is disconnected... 
      dbusservice["/Ac/ActiveIn/Connected"] = 0
      dbusservice["/Ac/ActiveIn/ActiveInput"] = 240          

    grid_relay_on = None
    try:
      if (ac_grid_ctrl == None) :
        ac_grid_ctrl = ShellyPy.Shelly(host_grid_ctl, timeout=1)
      grid_relay_on = ac_grid_ctrl.relay(0)['ison']
    except requests.exceptions.ConnectionError as e:
      pass

    # if there is a grid available
    if (grid_relay_on != None):
      # if the grid relay is on
      if (grid_relay_on) :
        # zero export to grid
        if (ac_in_total_power < 0 or (ac_in_total_power > 10 and ac_in_total_power < 100)) :
          zero_export_countdown -= 1
          logger.debug("!!!!!!!! Countdown: {0}".format(zero_export_countdown))
        else :
          zero_export_countdown = 5

        if (zero_export_countdown <= 0) :
          # drop ac relay
          ac_grid_control(False)
          
          logger.debug("!!!!!!!!!!!!!!!!!! GRID OFF!!!!!!!!!!!!!!")



        logger.info("Grid AC: {0}V, L1 Power: {1}W, L2 Power: {2}W, Total Power: {3}W"\
          .format(ac_in_l1_voltage, ac_in_l1_power, ac_in_l2_power, ac_in_total_power))

      else : # grid relay is off

        # if SOC is low, turn on grid
        if (soc <= 5.0 or storm_warning) :
          ac_grid_control(True)
          logger.debug("!!!!!!!!!!!!!!!! GRID ON!!!!!!!!!!!!!")

        logger.info("Grid AC: Available, Relay OFF")
    else :
      logger.info("Grid AC: OFFLINE")

    pass
    time.sleep(1)

#----------
def ac_loads_batt_handler():
  logger.debug("start ac loads battery thread")
  ac_loads = None

  while 1:

    LN_voltage = 0
    L1_power = 0
    L2_power = 0
    L1_reactive_power = 0
    L2_reactive_power = 0

    try:
      if (ac_loads == None) :
        ac_loads = ShellyPy.Shelly(host_ac_loads, timeout=1)

      relay_data = ac_loads.relay(0)
      ison = relay_data['ison']

      first_emeter_data = (ac_loads.emeter(0))
      second_emeter_data = (ac_loads.emeter(1))

      LN_voltage = round(first_emeter_data['voltage'], 2)
      #L2_voltage = second_emeter_data['voltage']

      L1_power = first_emeter_data['power']
      L2_power = second_emeter_data['power']
      L1_reactive_power = first_emeter_data['reactive']
      L2_reactive_power = second_emeter_data['reactive']

      global soc

      #get some data from the Victron BUS, invalid data returns NoneType
      raw_soc = dbusmonitor.get_value('com.victronenergy.system', '/Dc/Battery/Soc')
      if (raw_soc == None) :
        logger.debug("SOC is invalid")
        global keep_running
        keep_running = False
        sys.exit()
      else :
        soc = raw_soc

      time_to_go = dbusmonitor.get_value('com.victronenergy.system', '/Dc/Battery/TimeToGo')
      batt_volt = dbusmonitor.get_value('com.victronenergy.system', '/Dc/Battery/Voltage')
      batt_current = round(dbusmonitor.get_value('com.victronenergy.system', '/Dc/Battery/Current'), 1)
      batt_power = dbusmonitor.get_value('com.victronenergy.system', '/Dc/Battery/Power')
      batt_consumed_ah = round(dbusmonitor.get_value('com.victronenergy.system', '/Dc/Battery/ConsumedAmphours'), 1)
      
      pv_current = dbusmonitor.get_value('com.victronenergy.system', '/Dc/Pv/Current')
      if (pv_current == None):
        pv_current = 0.0

      pv_ac_l1_pwr = dbusmonitor.get_value('com.victronenergy.system', '/Ac/PvOnOutput/L1/Power')
      pv_ac_l2_pwr = dbusmonitor.get_value('com.victronenergy.system', '/Ac/PvOnOutput/L2/Power')
      if (pv_ac_l1_pwr == None):
        pv_ac_l1_pwr = 0
      if (pv_ac_l2_pwr == None):
        pv_ac_l2_pwr = 0        

      total_pv_power = pv_ac_l1_pwr + pv_ac_l2_pwr

      try:
        L1_delta_power = L1_power - pv_ac_l1_pwr
        L2_delta_power = L2_power - pv_ac_l2_pwr

        dbusservice["/Ac/Out/L1/P"] = L1_delta_power
        dbusservice["/Ac/Out/L2/P"] = L2_delta_power
        dbusservice["/Ac/Out/P"] =  L1_delta_power + L2_delta_power
        dbusservice["/Ac/Out/L1/F"] = 60
        dbusservice["/Ac/Out/L2/F"] = 60
        dbusservice["/Ac/Out/L1/V"] = LN_voltage
        dbusservice["/Ac/Out/L2/V"] = LN_voltage

        dbusservice["/Ac/Out/L1/I"] = round(L1_power / LN_voltage, 2)
        dbusservice["/Ac/Out/L2/I"] = round(L2_power / LN_voltage, 2)


        # state = 0:Off, 1:Low Power, 2:Fault, 3:Bulk, 4:Absorb, 5:Float, 6:Storage, 7:Equalize, 8:Passthrough 9:Inverting 
        #         10:Assisting, 11:Power Supply Mode, 12:Unknown
        # push charging state to dbus
        vebusChargeState = 0
        systemState = 0

        #logger.info("SysState: {0}, InvOn: {1}".format(systemState, inverter_on))

        # absorbtion (top balance) happens between 14.2-14.6 volts. 

        if (LN_voltage > 100):
          systemState = 9
          if (batt_volt < 56.8 and batt_current > 10):
            vebusChargeState = 1
            systemState = 3
          if (batt_volt > 56.8):
            vebusChargeState = 2
            systemState = 4

        dbusservice["/VebusChargeState"] = vebusChargeState
        dbusservice["/State"] = systemState

        dbusservice["/Dc/0/Voltage"] = round(batt_volt, 2)
        dbusservice["/Dc/0/Current"] = round(batt_current, 2)
        dbusservice["/Dc/0/Power"] = batt_power

      except Exception as e:
        print(e)

      # print status
      logger.info("L-N: {0}V, L1 Power: {1}W, L2 Power: {2}W, Total Power: {3}W"\
        .format(LN_voltage, L1_power, L2_power, L1_power+L2_power))
      logger.info("L1 Reactive Power: {0} VAR, L2 Reactive Power: {1} VAR"\
        .format(L1_reactive_power, L2_reactive_power))

      if (time_to_go == None):
        ttc = "TTG: INF"
      else:
        ttc = "TTG: {0}".format(round(time_to_go / 3600, 1))
        
      if (batt_current > 0.1):
        ttc = abs(round(batt_consumed_ah / batt_current,1))
        ttc = "TTC: {0}".format(ttc)

      #print (round(time_to_go / 3600, 1))
      logger.info("Battery: {0:.1f}%, {1:.2f}V, Current: {2}A, Consumed: {3} ah, {4} hrs"\
        .format(soc, batt_volt, batt_current, batt_consumed_ah, ttc))

      logger.info("AC PV: Relay On: {0}, PV Power: {1}W"\
        .format(ison, int(total_pv_power)))

      print
    #except requests.exceptions.RequestException as e:
    except Exception as e:
      logger.debug(e)
      time.sleep(5)
    time.sleep(1)


#----------
def exit(signal, frame):
  global keep_running
  keep_running = False


#----------
def main():
  logger.info("Driver start")

  stream_thread = threading.Thread(target=ac_loads_batt_handler)
  stream_thread.setDaemon(True)
  stream_thread.start()

  ac_grid_thread = threading.Thread(target=ac_grid_handler)
  ac_grid_thread.setDaemon(True)
  ac_grid_thread.start()

  global _mainloop
  _mainloop = gobject.MainLoop()
  gobject.threads_init()
  context = _mainloop.get_context()

  signal.signal(signal.SIGINT, exit)

  while keep_running:
    context.iteration(True)

  logger.info("Driver stop")

if __name__ == '__main__':
  main()
