# Home Assistant P2PCam
Home assistant component to retrieve camera images from cameras using the p2p protocol

First of all i just wrote the original connection and retrieval process has been made by [Jheyman](https://github.com/jheyman/) in his [videosurveillance script](https://github.com/jheyman/videosurveillance/).
I rewrote it to run as a class instead of an application and added the home assitant code to it.

So i had this [chinese camera](https://nl.aliexpress.com/item/Phone-monitor-P2P-Free-DDNS-Ontop-RT8633-HD-1-4-CMOS-1-0MP-Network-IP-Camera/990524792.html) laying around, it had this feature that you could access it from outside your home without the need for port forwarding. However after a couple of years this brand dissappeared and with it their services so i couldn't connect to it outside of my own network using [this app](https://play.google.com/store/apps/details?id=x.p2p.cam).

Which made owning this camera quite useless. But i had since gotten into Home Asssistant and got the idea to get it working in there since my instance ran locally so it should be able to access the camera.

## Installation
Place these files:
 * `camera.py`
 * `manifest.json`

In `<config directory>/custom_components/p2pcam/`.

Once this is done you can move on to configuring it.
```
camera:
  - platform: p2pcam
    name: <camera name>
    host: <the ip address of your home assistant>
    ip_address: <the ip address of your camera>
```
e.g.
```
camera:
  - platform: p2pcam
    name: ontop
    host: 192.168.178.5
    ip_address: 192.168.178.9
```

The connection method of these cameras seem quite dodgy so it may take a little while sometimes for the image to be fetched. This will no longer be a problem once a connection has been established and the stream is being received.
### Disclaimer
I am not an experienced python or home assistant component developer. This is one of my first projects for this, i would love feedback and [Pull requests](https://github.com/indykoning/home-assistant-p2pcam/pulls) to improve this and maybe even get it into the core.
## To Do
 * I used to have support for a timestamp and flipping and rotating the image using the CV2 library. Since home assistant 0.92 i could not get this to work since i could not find the correct library to require.
