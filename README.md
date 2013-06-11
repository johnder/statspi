# StatsPi

There are a few options when picking out hosts for your wall of graphite graphs: get laptops to run them, nettops, or something tiny like that. But these all cost a lot of money, and they tend to be overkill for displaying and updating a few images on a screen.  At iHeartRadio, we decided to go the RaspberryPi route, not only because it is cheaper, but because it is damn cool to have everything we need to run a single graph TV attached to and powered by the TV.

## The Story

When we first started out, we were running Chrome, which displayed a single page with a few graphs on it. As we discovered, Chrome would continually eat up more and more memory, to the point that the OS killed the process, just to display graphs. In an effort to be more light-weight, we tried Midori, and the same thing happened. The crazy part is that we absolutely could not replicate this on any of our other machines, just on the Pis. One late-night coding session later, StatsPi was born, sporting centralized graph-wall config, automatic graph distribution, and a tiny memory footprint that the Pis could handle.

## The Wall

![The Pi Wall](https://raw.github.com/iheartradio/statspi/master/wall.jpg)

## The Parts

1. 1 TV with a USB port that provides power (preferably 1080p with a 1x1 pixel mode for HDMI in (aka. no overscan)) per Pi
1. 1 [hdmi cable](http://www.amazon.com/dp/B00870ZHCQ) per Pi
1. 1 [micro usb cable](http://www.amazon.com/dp/B003ES5ZSW) per Pi
1. 1 [sdcard](http://www.amazon.com/dp/B003VNKNEG) per Pi
1. 1 [usb wifi dongle](http://www.amazon.com/dp/B005CLMJLU) per Pi, if you wish to use wifi
1. 1 [case](http://www.adafruit.com/products/1140) per Pi

## The Setup

1. Go through your normal routine of getting ONE of your [sdcards for you Pis all setup](http://elinux.org/RPi_Easy_SD_Card_Setup).  Go ahead, I'll wait
1. Mount that sdcard in a Pi, connect to a network, and run:

	```bash
	sudo aptitude install python-gtk2 x11-utils git
	git clone git://github.com/iheartradio/statspi.git
	cd statspi
	sudo pip install -e git://github.com/shazow/urllib3.git#egg=urllib3
	```

1. Set the Pi's hostname to something unique on your network and add that name to your config.  For ours, they're simply: pi0 .. piN
1. Update /etc/hosts: replace raspberrypi with the hostname of your Pi (the pi0 .. piN from above).
1. Go setup your [configuration (see the Config section)](#the-config).
1. Disable the Pi's default screensaver, create and chmod u+x this script in ~/bin/disable_screensaver

	```bash
	#!/bin/bash

	xset s off
	xset -dpms
	xset s noblank
	```

1. Make the application start on boot by adding/creating: ~/.config/lxsession/LXDE/autostart

	```
	/home/pi/bin/disable_screensaver
	@python /home/pi/statspi/statspi.py http://URL.COM/TO/YOUR/config.json
	```

1. If you're using WiFi, you're going to want to make it [reconnect on drop](#wifi-reconnect).
1. Reboot and test to make sure it all works.
1. Plop that sdcard back into a computer and make a copy of it:

	```bash
	sudo dd if=/dev/<SDCARD> bs=4M | bzip2 > statspi.img.bz2
	```

1. Create images for the rest of your sdcards.

	```bash
	bzcat statspi.img.bz2 | sudo dd of=/dev/<SDCARD> bs=4M
	```

1. Mount the sdcard, change the pi's hostname in /etc/hostname to something unique and add that name to your config.
1. Rinse and repeat.

## Wifi Reconnect

WiFi on the Pi can be a bit spotty, so it's best to have it [reconnect on drop by watching it](http://www.raspberrypi.org/phpBB3/viewtopic.php?f=26&t=16054).

1. Assuming you have passwordless sudo (default on raspbian), create: ~/bin/watch_wifi

	```bash
	#!/bin/bash

	while true ; do
		if sudo ifconfig wlan0 | grep -q "inet addr:" ; then
			sleep 60
		else
			sudo ifdown --force wlan0
			sudo ifup --force wlan0
			sleep 10
		fi
	done
	```

1. Append to ~/.config/lxsession/LXDE/autostart:

	```
	@/home/pi/bin/watch_wifi
	```

## The Config

The config file for StatsPi is essential for keeping everything on your wall up-to-date.  Below is an example config that MUST be accessible to every Pi.

| Key                  | Explanation
| -------------------- | -----------
| graphUpdateInterval  | How often the displayed graphs should be updated.
| configUpdateInterval | How often the configuration file should be polled for changes. Any changes will update the entire wall.
| graphiteWebRoot      | Where your graphite web app lives (the http://graphite.webapp.com part of http://graphite.webapp.com/render/)
| bgcolor              | The background color to use for the app and graph backgrounds (so they match)
| clusters             | Configuration for all of you statspi clusters. Typically, there is only 1 cluster, and in this case, there is no need to specify which suites should be displayed (by default, all are). If, however, you have multiple teams, and each team wants its own graphs on their local TV, then you can setup multiple clusters, giving each any number of suites. In the example below, there are three clusters: one main cluster will all of the suites, and two small clusters with ONLY the graphs from Suite 1 or Suite 2.
| params               | The default parameters that will be used to build graph URLs. [Any normal graphite parameter works.](http://graphite.readthedocs.org/en/latest/render_api.html#graph-parameters)
| graphs               | The list of graphs, broken down by suite. Each suite is an array of graphs that contains at least a title and an array of targets. Graphs are organized alphabetically by their suite name (put onto screens in the order of `hosts`), but config order is maintained amongst the graphs in each suite. Suites are just a logical grouping of graphs, and the suite name is prepended to the title of the graph. Any extra parameter given in a graph config overrides the default parameters in `params`.

```json
{
	"graphUpdateInterval": 10,
	"configUpdateInterval": 60,
	"graphiteWebRoot": "http://url.to.your.graphite.root",
	"bgcolor": "#333333",
	"clusters": [
        {
            "hosts": [
                "pi0",
                "pi1",
                "pi2",
                "pi3"
            ]
        },
        {
            "suites": [
                "Suite 1"
            ],
            "hosts": [
                "pi4",
                "pi5"
            ]
        },
        {
            "suites": [
                "Suite 2"
            ],
            "hosts": [
                "pi6"
            ]
        }
    ],
	"params": {
		"areaAlpha": 0.3,
		"areaMode": "all",
		"drawNullAsZero": true,
		"fgcolor": "#f0f0f0",
		"from": "-30min",
		"hideLegend":  true,
		"majorGridLineColor": "#444444",
		"minorGridLineColor": "#444444"
	},
	"graphs": {
		"Suite 1": [
			{
				"title": "Hits Per Second",

				"targets": [
					"my.site.hits_per_second"
				]
			},
			{
				"title": "Logins Per Second",

				"targets": [
					"my.site.logins_per_second"
				]
			}
		],

		"Suite 2": [
			{
				"title": "Parties Per Second",

				"targets": [
					"my.site.parties_per_second"
				]
			}
		]
	}
}
```
