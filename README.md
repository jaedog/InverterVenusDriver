### THIS IS A WORK IN PROGRESS -- YMMV, NO WARRANTY EXPRESSED OR IMPLIED. YOU CAN ENDANGER YOURSELF AND OTHERS.

# Inverter Venus Driver
This project integrates any generic A/C inverter with the Victron Venus OS. It utilizes Shelley EM hardware to monitor power. The software runs on the Venus OS device as a Venus driver and uses the Venus dbus to read/write data for use with the Venus device.

### Kudos to Victron Energy
Victron Engergy has provided much of the Venus OS architecture under Open Source copyright. This framework allows independent projects like this to exist. Even though we are using non-Victron hardware, we can include it into the Victron ecosystem with other Victron equipment. Victron stated that although they would not assist, they would not block it. Send support to Victron Energy by buying their products!

Tested with RPi 3B - v2.60 Build 20200906135923

### Install

The provided install.sh script will copy files download dependencies and should provide a running configuration. It will not setup valid configuration values so don't expect this to be plug and play:

1. enable root access on your Venus device (see useful reading below)
2. from root login on the venus root home directory
3. run  wget https://raw.githubusercontent.com/jaedog/InverterVenusDriver/main/install/install.sh
4. run sh install.sh
5. answer Y to the install of the driver
6. answer Y to the dependencies (unless they are already installed)

### Useful Reading

Venus Developmental Info see https://github.com/victronenergy/venus/wiki/howto-add-a-driver-to-Venus .

Enable Root / SSH Access see https://www.victronenergy.com/live/ccgx:root_access#:~:text=Go%20to%20Settings%2C%20General,Access%20Level%20change%20to%20Superuser. 

Add additional modules (now handles by install script) sww https://github.com/victronenergy/venus/wiki/installing-additional-python-modules.
