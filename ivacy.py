#!/bin/sh
#
# This file is a part of Ivacy router applet.
#

## Externally generated options.
IVACY_APPLET_URL='http://router.ivacy.com'
IVACY_USER='username'
IVACY_PASS='password'
IVACY_EXPIRE='2020-12-20'
IVACY_BRANCH='main'

ARCH=$(uname -m)
if [ -e /www/tomato.js ]; then FIRMWARE="tomato"
else FIRMWARE="ddwrt"
fi

## Install options
IVACY_VERSION_URL="$IVACY_APPLET_URL/cgi-bin/applet-cgi.py?action=version&arch=$ARCH&firmware=$FIRMWARE&branch=$IVACY_BRANCH"
IVACY_INSTALL_URL="$IVACY_APPLET_URL/cgi-bin/applet-cgi.py?action=download&arch=$ARCH&firmware=$FIRMWARE&branch=$IVACY_BRANCH"
IVACY_HWCHECK_URL="$IVACY_APPLET_URL/cgi-bin/applet-cgi.py?action=hwcheck&arch=$ARCH&firmware=$FIRMWARE&branch=$IVACY_BRANCH"
IVACY_JFFS2_ROOT=/jffs/ivacy
IVACY_TMP_ROOT=/tmp/ivacy
IVACY_OVPN_MIN_MAJOR=2
IVACY_OVPN_MIN_MINOR=1
IVACY_NVRAM_BYTES=$((5*1024))
IVACY_USE_JFFS2=0
IVACY_APPLET_SIZE=$((2*1024))
IVACY_DDWRT_BUILD=13309 # MyPage requires 13309 build
IVACY_TOMATO_KVER=2.6
IVACY_VERSION=`/tmp/www/cgi-bin/ivacy.cgi -v 2>&1 > /dev/null | grep 'IVACY_APPLET_VERSION=' | tr '=' ' ' | awk '{print $2}'`
IVACY_DEVICE=$(nvram get DD_BOARD)

## These are hardcoded inside other scripts. You should not change them.
IVACY_WWW=/tmp/www
IVACY_TMP=/tmp/ivacy

echo "Machine name..." `uname -m`
echo "System info..." `cat /proc/cpuinfo | grep -i 'system type' | sed 's/[A-Za-z\t ]*:[\t ]*\(.*\)/\1/' || echo 'could not detect'`
echo "CPU model..." `cat /proc/cpuinfo | grep -i 'cpu model' | sed 's/[A-Za-z\t ]*:[\t ]*\(.*\)/\1/' || echo 'could not detect'`
echo -n "Check Firmware..."
DDWRT_BUILD=`/sbin/softwarerevision 2> /dev/null | grep -oE "^[0-9]+" `
if [ "$FIRMWARE" = "ddwrt" ]; then
    if ! [ "$DDWRT_BUILD" ]; then
        echo "Could not detect DDWRT build number. Aborting."
        exit 1
    fi
    if [ "$DDWRT_BUILD" -lt "$IVACY_DDWRT_BUILD" ]; then
        echo "Ivacy Applet can only run $IVACY_DDWRT_BUILD DD-WRT builds or newer."
        echo "Your router runs $DDWRT_BUILD build. Aborting."
        exit 1
    fi
elif [ "$FIRMWARE" = "tomato" ]; then
    KERNEL=`cat /proc/version | cut -d' ' -f3 | cut -d'.' -f1-2`
    if ! [ "$KERNEL" ] || [ "$KERNEL" != "$IVACY_TOMATO_KVER" ]; then
        echo "Warning: only tomato with $IVACY_TOMATO_KVER kernel builds are supported."
    fi
else
    echo "Your router has unsupported firmware. Ivacy applet can only be "
    echo " installed on DDWRT-$IVACY_DDWRT_BUILD or Tomato Firmware. Aborting."
    exit 1
fi
echo $FIRMWARE

## Check if applet is already installed
echo -n "Detect Ivacy Applet... "
IVACY_OLD_ROOT=`nvram get ivacy_root`
if [ "$IVACY_OLD_ROOT" ]; then
    # Print old applet version in the log
    IVACY_OLDVER=""
    IVACY_OLDCGI=$IVACY_OLD_ROOT/www/cgi-bin/ivacy.cgi
    if [ -f "$IVACY_OLDCGI" ]; then
        VERSION=`"$IVACY_OLDCGI" -v 2>&1 > /dev/null | grep 'IVACY_APPLET_VERSION=' | tr '=' ' ' | awk '{print $2}'`
    fi
    echo "$VERSION in /tmp/ivacy"
    IVACY_UNINSTALL=$IVACY_OLD_ROOT/www/scripts/ivacy_uninstall.sh
    if [ -d "$IVACY_OLD_ROOT" ]; then
        [ -f $IVACY_UNINSTALL ] && $IVACY_UNINSTALL reinstall
    else
        ## Reset settings to defaults on the first startup
        mkdir -p $IVACY_TMP
        touch $IVACY_TMP/.reset_to_defaults
    fi
else
    echo "not found"
fi

## Check if PPTP is supported by the router
#echo -n "Check PPTP support... "
#if [ "$FIRMWARE" = "ddwrt" ]; then
#    PPTP_BIN=`which pptp`
#    if [ "$PPTP_BIN" ]; then
#        echo "found $PPTP_BIN"
#        USE_PPTP=1
#    else
#        echo "not found (PPTP will not be available)"
#        USE_PPTP=0
#    fi
#elif [ "$FIRMWARE" = "tomato" ]; then
#    PPPD_BIN=`which pppd`
#    PPTP_PLUGIN=/usr/lib/pppd/pptp.so
#    if [ -f $PPTP_PLUGIN ] && [ -f "$PPPD_BIN" ]; then
#        echo "found $PPTP_PLUGIN"
#        USE_PPTP=1
#    else
#        echo "not found (PPTP will not be available)"
#        USE_PPTP=0
#    fi
#fi

## Check if we can deploy on JFFS2 partition
if [ "$IVACY_USE_JFFS2" -eq 1 ]; then
    echo -n "Check if we can install on JFFS... "
    HAS_JFFS2=`grep jffs2 /proc/filesystems`
    JFFS2_DEVICE=`mount -t jffs2 | head -n 1 | awk '{print $1}'`
    JFFS2_MOUNT=`mount -t jffs2 | head -n 1 | awk '{print $3}'`
    JFFS2_KBYTES=`df "$JFFS2_MOUNT" 2> /dev/null | tail -n+2 | head -n 1 | awk '{print $4}'`
    if ! [ $HAS_JFFS2 ] || ! [ $JFFS2_KBYTES ] || ! [ $JFFS2_DEVICE ] || ! [ $JFFS2_MOUNT ]; then
        echo "jffs2 partiton not found. "
        echo "Applet will be reinstalled upon next reboot."
    elif [ "$JFFS2_KBYTES" -lt "$IVACY_APPLET_SIZE" ]; then
        echo "jffs2 partition has not enough free space."
        echo "Ivacy applet requires $(((IVACY_APPLET_SIZE+1023)/1024)) MB of free space"
        echo "where is only $((JFFS2_KBYTES/1024)) available."
    else
        USE_JFFS2=1
        echo "found in $JFFS2_MOUNT"
    fi
fi

## Check NVRAM available space
echo -n "Check available nvram space... "
if [ "$FIRMWARE" = "ddwrt" ]; then
    NVRAM_BYTES=`nvram show 2>&1 > /dev/null | sed -r 's/size\: ([0-9]*) bytes \(([0-9]*) left\)/\2/g'`
    ## TODO uncomment me and test me
    # NVRAM_BYTES=`nvram show | tail -n 1 | cut -d' ' -f4`
elif [ "$FIRMWARE" = "tomato" ]; then
    NVRAM_BYTES=`nvram show | tail -n 1 | cut -d' ' -f6`
fi
if [ "$NVRAM_BYTES" ]; then
    if [ "$NVRAM_BYTES" -lt "$IVACY_NVRAM_BYTES" ]; then
        echo "less than $(((IVACY_NVRAM_BYTES+1023)/1024)) KB free. Abort. "
        exit 1
    else
        echo "$NVRAM_BYTES bytes available"
    fi
else
    echo "not found. Aborting."
    exit 1
fi

## Check OpenVPN binaries and version
#echo -n "Check OpenVPN version... "
#OPENVPN_BIN=`which openvpn`
#OPENVPN_VERSION=`$OPENVPN_BIN --version 2> /dev/null | head -n 1 | cut -d' ' -f 2`
#OPENVPN_MAJOR=`echo $OPENVPN_VERSION | cut -d'.' -f1`
#OPENVPN_MINOR=`echo $OPENVPN_VERSION | cut -d'.' -f2`
#if ! [ "$OPENVPN_BIN" ]; then
#    echo "openvpn not found (abort installation)"
#    exit 1
#elif [ "$OPENVPN_MAJOR" -lt "$IVACY_OVPN_MIN_MAJOR" ] ||
#         ( [ "$OPENVPN_MAJOR" -eq "$IVACY_OVPN_MIN_MAJOR" ] && [ "$OPENVPN_MINOR" -lt "$IVACY_OVPN_MIN_MINOR" ] ); then
#    echo "OpenVPN is outdated. Aborting."
#    echo "Please update your OpenVPN to version at least $IVACY_OVPN_MIN_MAJOR.$IVACY_OVPN_MIN_MINOR"
#    exit 1
#else
#    echo "$OPENVPN_MAJOR.$OPENVPN_MINOR found"
#fi

## Check PPTP and OpenVPN for installation
echo -n "Check PPTP and OpenVPN support... "
if [ "$FIRMWARE" = "ddwrt" ]; then
	PPTP_BIN=`which pptp`
	OPENVPN_BIN=`which openvpn`
	OPENVPN_VERSION=`$OPENVPN_BIN --version 2> /dev/null | head -n 1 | cut -d' ' -f 2`
	OPENVPN_MAJOR=`echo $OPENVPN_VERSION | cut -d'.' -f1`
	OPENVPN_MINOR=`echo $OPENVPN_VERSION | cut -d'.' -f2`
	if ! ( [ "$PPTP_BIN" ] && [ $OPENVPN_BIN ] ); then
		echo "OpenVPN and PPTP not found (abort installation)"
		USE_PPTP=0		
		exit 1
	elif [ "$OPENVPN_MAJOR" -lt "$IVACY_OVPN_MIN_MAJOR" ] ||
         ( [ "$OPENVPN_MAJOR" -eq "$IVACY_OVPN_MIN_MAJOR" ] && [ "$OPENVPN_MINOR" -lt "$IVACY_OVPN_MIN_MINOR" ] ); then
		if [ "$PPTP_BIN" ]; then
			echo "found $PPTP_BIN"
			echo "Please update your OpenVPN to version at least $IVACY_OVPN_MIN_MAJOR.$IVACY_OVPN_MIN_MINOR"
			USE_PPTP=1
		else
			echo "not found (PPTP will not be available)"
			echo "Please update your OpenVPN to version at least $IVACY_OVPN_MIN_MAJOR.$IVACY_OVPN_MIN_MINOR"
			USE_PPTP=0
			exit 1
		fi
	elif [ "$PPTP_BIN" ] && [ $OPENVPN_BIN ]; then
		echo "found $PPTP_BIN"
		echo "OpenVPN: $OPENVPN_MAJOR.$OPENVPN_MINOR found"
		USE_PPTP=1
	elif [ "$PPTP_BIN" ] && ! [ $OPENVPN_BIN ]; then
		echo "found $PPTP_BIN"
		echo "OpenVPN not found"
		USE_PPTP=1
	else
		echo "not found (PPTP will not be available)"
		echo "OpenVPN: $OPENVPN_MAJOR.$OPENVPN_MINOR found"
		USE_PPTP=0
	fi
elif [ "$FIRMWARE" = "tomato" ]; then
	PPPD_BIN=`which pppd`
	PPTP_PLUGIN=/usr/lib/pppd/pptp.so
	OPENVPN_BIN=`which openvpn`
	OPENVPN_VERSION=`$OPENVPN_BIN --version 2> /dev/null | head -n 1 | cut -d' ' -f 2`
	OPENVPN_MAJOR=`echo $OPENVPN_VERSION | cut -d'.' -f1`
	OPENVPN_MINOR=`echo $OPENVPN_VERSION | cut -d'.' -f2`
	if ! ( [ -f $PPTP_PLUGIN ] && [ -f "$PPPD_BIN" ] && [ $OPENVPN_BIN ] ); then
		echo "OpenVPN and PPTP not found (abort installation)"
		USE_PPTP=0		
		exit 1
	elif [ "$OPENVPN_MAJOR" -lt "$IVACY_OVPN_MIN_MAJOR" ] ||
         ( [ "$OPENVPN_MAJOR" -eq "$IVACY_OVPN_MIN_MAJOR" ] && [ "$OPENVPN_MINOR" -lt "$IVACY_OVPN_MIN_MINOR" ] ); then
		if [ -f $PPTP_PLUGIN ] && [ -f "$PPPD_BIN" ]; then
			echo "found $PPTP_PLUGIN"
			echo "Please update your OpenVPN to version at least $IVACY_OVPN_MIN_MAJOR.$IVACY_OVPN_MIN_MINOR"
			USE_PPTP=1
		else
			echo "not found (PPTP will not be available)"
			echo "Please update your OpenVPN to version at least $IVACY_OVPN_MIN_MAJOR.$IVACY_OVPN_MIN_MINOR"
			USE_PPTP=0
			exit 1
		fi
	elif [ -f $PPTP_PLUGIN ] && [ -f "$PPPD_BIN" ] && [ $OPENVPN_BIN ]; then
		echo "found $PPTP_PLUGIN"
		echo "OpenVPN: $OPENVPN_MAJOR.$OPENVPN_MINOR found"
		USE_PPTP=1
	elif [ -f $PPTP_PLUGIN ] && [ -f "$PPPD_BIN" ] && ! [ $OPENVPN_BIN ]; then
		echo "found $PPTP_PLUGIN"
		echo "OpenVPN not found"
		USE_PPTP=1
	else
		echo "not found (PPTP will not be available)"
		echo "OpenVPN: $OPENVPN_MAJOR.$OPENVPN_MINOR found"
		USE_PPTP=0
	fi
fi

## Make final decision about installation dir
if [ $USE_JFFS2 ]; then
    IVACY_ROOT=$IVACY_JFFS2_ROOT
else
    IVACY_ROOT=$IVACY_TMP_ROOT
fi

echo -n "Check CPU arch support... "
HWCHECK=`wget -q -O - "$IVACY_HWCHECK_URL"`;
if [ "$HWCHECK" = "OK" ]; then
    echo "Supported"
else
    echo "$HWCHECK"
    echo "Your router is not supported. Aborted."
    exit 1
fi

BOOTSTRAP_ENTRY="
while ! [ -f $IVACY_TMP/.lock ] ; do
    mkdir -p $IVACY_ROOT/..;
    wget \"$IVACY_INSTALL_URL\" -q -O - | gunzip -c | tar -x -C $IVACY_ROOT/..;
    wget \"$IVACY_INSTALL_URL\" -q -O - | tar -x -C $IVACY_ROOT/..;
    $IVACY_ROOT/www/scripts/ivacy_startup.sh;
    sleep 5;
done
"

echo -n "Init nvram... "
nvram set ivacy_root="$IVACY_ROOT"
nvram set ivacy_bootstrap="$BOOTSTRAP_ENTRY"
nvram set ivacy_pptp="$USE_PPTP"
#nvram set ivacy_user="$IVACY_USER"
#nvram set ivacy_pass="$IVACY_PASS"
nvram set ivacy_expire="$IVACY_EXPIRE"
nvram set ivacy_version_url="$IVACY_VERSION_URL"
nvram set ivacy_firmware="$FIRMWARE"
nvram set ivacy_update_versionid=""
nvram set ivacy_update_version=""
nvram set ivacy_update_timestamp=""

RUN_BOOTSTRAP='eval `nvram get ivacy_bootstrap`;'
RC_PARAM=""
if [ "$FIRMWARE" = "ddwrt" ]; then
    RC_PARAM=rc_startup
elif [ "$FIRMWARE" = "tomato" ]; then
    RC_PARAM=script_init
fi

nvram set $RC_PARAM="$RUN_BOOTSTRAP$(nvram get $RC_PARAM|sed s/"$RUN_BOOTSTRAP"//g)"
nvram commit >& /dev/null

echo "done"

echo "Installed in /tmp/ivacy"

echo "Starting..."
eval "$BOOTSTRAP_ENTRY"
if [ -f $IVACY_TMP/.lock ]; then
    echo "Started"
else
    echo "Aborted"
fi

DATA_SEND="{\"device_type\":\"DDWRT\",\"applet_version\":\"$IVACY_VERSION\",\"device_name\":\"$IVACY_DEVICE\"}"
#$IVACY_WWW/scripts/https_client -m POST -h "Content-Type: application/x-www-form-urlencoded" -h "User-agent: ivacy-agent" -d "$DATA_SEND" -a null -e RouterApplet_Install
