#!/bin/bash

# for testing purposes
#ROOT_DIR="/tmp/venus"
#mkdir -p ${ROOT_DIR}/data/etc
#mkdir -p ${ROOT_DIR}/var/log
#mkdir -p ${ROOT_DIR}/service
#mkdir -p ${ROOT_DIR}/etc/udev/rules.d
ROOT_DIR=""

# download this script:
# wget https://raw.githubusercontent.com/jaedog/InverterVenusDriver/main/install/install.sh

echo
echo "This generic inverter venus driver uses Shelly EM power meter hardware to monitor AC power parameters"
echo
echo "This script requires internet access to install dependencies and software."
echo
echo "Install Generic Inverter driver on Venus OS at your own risk?"
read -p "[Y to proceed] " -n 1 -r

echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  echo "Install dependencies (pip and python libs)?"
  read -p "[Y to proceed] " -n 1 -r
  echo    # (optional) move to a new line
  if [[ $REPLY =~ ^[Yy]$ ]]
  then

    echo "==== Download and install dependencies ===="
    opkg update
    opkg install python-misc python-distutils python-numbers python-html python-ctypes python-pkgutil
    opkg install python-unittest python-difflib python-compile gcc binutils python-dev python-unixadmin python-xmlrpc

    wget https://bootstrap.pypa.io/get-pip.py
    python get-pip.py
    rm get-pip.py

    #pip install python-can
    #pip install python-statemachine
    pip install pyyaml
    pip install ShellyPy
  fi

	echo "==== Download driver and library ===="
  wget https://github.com/jaedog/InverterVenusDriver/archive/refs/heads/main.zip
	unzip -qo main.zip
	rm main.zip
  
	echo "==== Install Inverter driver ===="
	DBUS_NAME="dbus-inverter"
	DBUS_DRV_DIR="${ROOT_DIR}/data/etc/${DBUS_NAME}"

	mkdir -p ${ROOT_DIR}/var/log/${DBUS_NAME}
	mkdir -p ${DBUS_DRV_DIR}
	cp -R  InverterVenusDriver-main/dbus-inverter/* ${ROOT_DIR}/data/etc/${DBUS_NAME}

  # replace inverter svg with gerneric grey inverter svg
  cp InverterVenusDriver-main/assets/overview-inverter.svg ${ROOT_DIR}/opt/victronenergy/themes/ccgx/images

	chmod +x ${ROOT_DIR}/data/etc/${DBUS_NAME}/dbus-inverter.py
	chmod +x ${ROOT_DIR}/data/etc/${DBUS_NAME}/service/run
	chmod +x ${ROOT_DIR}/data/etc/${DBUS_NAME}//service/log/run
	ln -s ${ROOT_DIR}/opt/victronenergy/vrmlogger/ext/ ${DBUS_DRV_DIR}/ext 
	ln -s ${DBUS_DRV_DIR}/service ${ROOT_DIR}/service/${DBUS_NAME}

  # remove archive files
  rm -rf InverterVenusDriver-main/

  echo
	echo "To finish, reboot the Venus OS device"
fi
